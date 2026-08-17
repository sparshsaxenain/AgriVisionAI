"""Natural-language agent API backed by LangGraph and NVIDIA NIM."""
from __future__ import annotations

import logging
import json
import re
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.agent import AgentService, get_agent_service
from backend.api.deps import bearer, current_user
from backend.api.diagnoses import analyze_crop_upload, analyze_image_upload, persist_diagnosis
from backend.core.config import get_settings
from backend.db.database import get_db
from backend.models import Crop, Farm, User
from backend.schemas.api import DiagnosisPreview, DiagnosisSave
from backend.services.crop_catalog import is_supported_crop_type

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["Agentic AI"])


class AgentQuery(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    thread_id: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    language: Literal["en", "hi", "ta"] = "en"


class AgentResponse(BaseModel):
    answer: str
    thread_id: str
    model: str
    tool_calls: list[dict[str, Any]]


class AgentImageResponse(AgentResponse):
    image_analysis: DiagnosisPreview
    diagnosis_context: dict[str, int] | None = None
    saved_diagnosis_id: int | None = None


def _wants_saved_diagnosis(query: str) -> bool:
    """Recognize explicit persistence language without delegating the safety decision to the LLM."""
    text = query.casefold()
    if re.search(
        r"\b(?:do\s+not|don't|dont|not\s+to)\s+(?:save|add|record|log|store)\b"
        r"|\bwithout\s+(?:saving|adding|recording|logging|storing)\b",
        text,
    ) or re.search(r"(?:मत|नहीं)\s*(?:सहेज|सेव|दर्ज|रिकॉर्ड|जो[ड़ड़])|(?:सहेज|सेव|दर्ज|रिकॉर्ड|जो[ड़ड़])\s*मत", text):
        return False
    return bool(
        re.search(r"\b(?:save|record|log|store)\b", text)
        or re.search(r"\badd\s+(?:it|this|the\s+(?:diagnosis|analysis|result)|(?:diagnosis|analysis|result))\b", text)
        or re.search(r"(?:सहेज|सेव|दर्ज|रिकॉर्ड|जो[ड़ड़])", text)
    )


def _resolve_image_context(
    db: Session,
    user_id: int,
    query: str,
    farm_id: int | None,
    crop_id: int | None,
) -> tuple[int, int]:
    rows = db.execute(
        select(Crop, Farm)
        .join(Farm, Farm.id == Crop.farm_id)
        .where(Farm.farmer_id == user_id, Crop.status == "Active")
    ).all()
    candidates = [
        (crop, farm) for crop, farm in rows
        if is_supported_crop_type(crop.crop_name)
        and (farm_id is None or farm.id == farm_id)
        and (crop_id is None or crop.id == crop_id)
    ]
    if farm_id is not None and crop_id is not None:
        return farm_id, crop_id
    if len(candidates) == 1:
        crop, farm = candidates[0]
        return farm.id, crop.id

    query_text = query.casefold()
    scored = [
        (
            (2 if farm.farm_name.casefold() in query_text else 0)
            + (1 if crop.crop_name.casefold() in query_text else 0),
            crop,
            farm,
        )
        for crop, farm in candidates
    ]
    if scored:
        best_score = max(score for score, _, _ in scored)
        best = [(crop, farm) for score, crop, farm in scored if score == best_score and score > 0]
        if len(best) == 1:
            crop, farm = best[0]
            return farm.id, crop.id

    choices = "; ".join(f"{farm.farm_name} / {crop.crop_name}" for crop, farm in candidates[:8])
    if choices:
        raise HTTPException(
            400,
            "I could not determine which crop record this image belongs to. Mention the farm and crop in the query. "
            f"Available choices: {choices}.",
        )
    raise HTTPException(400, "No active crop supported by the image model was found. Add one in Farm Records first.")


@router.get("/status")
def agent_status(service: AgentService = Depends(get_agent_service)):
    return service.status()


@router.post("/query", response_model=AgentResponse)
def query_agent(
    payload: AgentQuery,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    user: User = Depends(current_user),
    service: AgentService = Depends(get_agent_service),
):
    if credentials is None:  # current_user normally handles this; keeps typing explicit.
        raise HTTPException(401, "Please sign in.")
    try:
        result = service.run(
            payload.query,
            credentials.credentials,
            user.id,
            payload.thread_id,
            response_language=payload.language,
        )
    except Exception:
        logger.exception("Agent run failed for user=%s", user.id)
        raise HTTPException(
            503,
            "The NVIDIA NIM agent is unavailable. Check NVIDIA_API_KEY, NVIDIA_NIM_BASE_URL, and NVIDIA_NIM_MODEL.",
        )
    return AgentResponse(
        answer=result.answer,
        thread_id=result.thread_id,
        model=result.model,
        tool_calls=result.tool_calls,
    )


@router.post("/query-with-image", response_model=AgentImageResponse)
async def query_agent_with_image(
    query: str = Form(..., min_length=2, max_length=2000),
    farm_id: int | None = Form(default=None),
    crop_id: int | None = Form(default=None),
    image: UploadFile = File(...),
    thread_id: str | None = Form(default=None, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$"),
    language: Literal["en", "hi", "ta"] = Form(default="en"),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    service: AgentService = Depends(get_agent_service),
):
    if credentials is None:
        raise HTTPException(401, "Please sign in.")
    save_requested = _wants_saved_diagnosis(query)
    resolved_farm_id: int | None = None
    resolved_crop_id: int | None = None
    if save_requested:
        resolved_farm_id, resolved_crop_id = _resolve_image_context(db, user.id, query, farm_id, crop_id)
        analysis = await analyze_crop_upload(resolved_farm_id, resolved_crop_id, image, db, user)
        mode_context: dict[str, Any] = {
            "mode": "save_requested",
            "storage": "The user explicitly requested this result be added to their records.",
            "farm_id": resolved_farm_id,
            "crop_id": resolved_crop_id,
        }
    else:
        analysis = await analyze_image_upload(
            image,
            persist_image=False,
            log_context=f"quick analysis user={user.id}",
        )
        mode_context = {
            "mode": "quick_analysis",
            "storage": "This is a standalone quick analysis. It is not linked to a farm or crop and is not saved.",
        }
    verified_context = json.dumps(
        {
            "source": "AgriVision crop image model",
            **mode_context,
            "result": analysis.model_dump(mode="json"),
        },
        ensure_ascii=False,
    )
    try:
        result = await run_in_threadpool(
            service.run,
            query,
            credentials.credentials,
            user.id,
            thread_id,
            verified_context,
            language,
        )
    except Exception:
        logger.exception("Image-assisted agent run failed for user=%s", user.id)
        if analysis.image_token:
            token = Path(analysis.image_token).name
            (get_settings().uploads_dir / token).unlink(missing_ok=True)
        raise HTTPException(
            503,
            "The image was analyzed, but the NVIDIA NIM agent is unavailable. Check the NVIDIA NIM configuration.",
        )
    saved_diagnosis_id = None
    if language == "hi":
        try:
            analysis.localized = await run_in_threadpool(service.localize_diagnosis, analysis, language)
        except Exception:
            logger.exception("Hindi image-analysis localization failed for user=%s", user.id)
    if save_requested and resolved_farm_id is not None and resolved_crop_id is not None:
        advisory_to_save = dict(analysis.advisory)
        if analysis.localized:
            advisory_to_save["_localizations"] = {language: analysis.localized["advisory"]}
            advisory_to_save["_display_names"] = {language: analysis.localized["display_name"]}
        diagnosis = persist_diagnosis(
            DiagnosisSave(
                farm_id=resolved_farm_id,
                crop_id=resolved_crop_id,
                image_token=analysis.image_token,
                predicted_class=analysis.predicted_class,
                display_name=analysis.display_name,
                confidence=analysis.confidence,
                severity=analysis.severity,
                advisory=advisory_to_save,
                model_version=analysis.model_version,
            ),
            db,
            user,
        )
        saved_diagnosis_id = diagnosis.id
    return AgentImageResponse(
        answer=result.answer,
        thread_id=result.thread_id,
        model=result.model,
        tool_calls=result.tool_calls,
        image_analysis=analysis,
        diagnosis_context=(
            {"farm_id": resolved_farm_id, "crop_id": resolved_crop_id}
            if save_requested and resolved_farm_id is not None and resolved_crop_id is not None
            else None
        ),
        saved_diagnosis_id=saved_diagnosis_id,
    )
