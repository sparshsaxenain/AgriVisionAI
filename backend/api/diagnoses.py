from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import current_user
from backend.core.config import get_settings
from backend.db.database import get_db
from backend.models import Crop, CropDiagnosis, Farm, User
from backend.schemas.api import DiagnosisOut, DiagnosisPreview, DiagnosisSave
from backend.services.advisory_service import AdvisoryService
from backend.services.alert_service import create_crop_alerts
from backend.services.crop_inference import get_crop_model
from backend.services.crop_catalog import supported_crop_types
from ml.preprocessing import open_rgb_image

router = APIRouter(prefix="/diagnosis", tags=["Crop Diagnosis"])
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png"}
logger = logging.getLogger(__name__)


def _owned_context(db: Session, user_id: int, farm_id: int, crop_id: int) -> tuple[Farm, Crop]:
    farm = db.scalar(select(Farm).where(Farm.id == farm_id, Farm.farmer_id == user_id))
    crop = db.scalar(select(Crop).where(Crop.id == crop_id, Crop.farm_id == farm_id))
    if not farm or not crop:
        raise HTTPException(404, "Farm or crop not found.")
    return farm, crop


async def analyze_crop_upload(
    farm_id: int,
    crop_id: int,
    image: UploadFile,
    db: Session,
    user: User,
) -> DiagnosisPreview:
    """Analyze an image for a known crop and retain it for an optional save."""
    _, crop = _owned_context(db, user.id, farm_id, crop_id)
    return await analyze_image_upload(
        image,
        crop_name=crop.crop_name,
        crop_stage=crop.crop_stage,
        persist_image=True,
        log_context=f"user={user.id} crop={crop_id}",
    )


async def analyze_image_upload(
    image: UploadFile,
    *,
    crop_name: str = "",
    crop_stage: str = "",
    persist_image: bool = False,
    log_context: str = "standalone image",
) -> DiagnosisPreview:
    """Run validated crop inference, optionally retaining the image for persistence."""
    suffix = Path(image.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, "Please upload a JPG, JPEG, or PNG image.")
    data = await image.read()
    settings = get_settings()
    if not data or len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(400, f"Image must be smaller than {settings.max_upload_mb} MB.")
    try:
        pil_image = open_rgb_image(data)
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(400, "The image could not be read. Please choose a clear JPG or PNG.")
    pil_image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    token = f"{uuid.uuid4().hex}.jpg" if persist_image else ""
    target = settings.uploads_dir / token if token else None
    if target is not None:
        # Local JPEG compression keeps retained images and API payloads small.
        pil_image.save(target, "JPEG", quality=82, optimize=True)
    try:
        model = get_crop_model()
        result = model.predict(pil_image, image.filename or "")
    except Exception:
        logger.exception("Crop prediction failed for %s", log_context)
        if target is not None:
            target.unlink(missing_ok=True)
        raise HTTPException(503, "Crop analysis is temporarily unavailable. Check the model configuration.")
    advisory = AdvisoryService().build(result.predicted_class, result.confidence, crop_name, crop_stage)
    confidence_label = advisory["confidence_label"]
    return DiagnosisPreview(
        **result.to_dict(), confidence_label=confidence_label, severity=advisory["severity"],
        advisory=advisory, image_token=token, mock_mode=model.is_mock,
    )


@router.post("/predict", response_model=DiagnosisPreview)
async def predict_crop(
    farm_id: int = Form(...),
    crop_id: int = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return await analyze_crop_upload(farm_id, crop_id, image, db, user)


@router.get("/supported-crops", response_model=list[str])
def supported_crops():
    return list(supported_crop_types())


def persist_diagnosis(payload: DiagnosisSave, db: Session, user: User) -> CropDiagnosis:
    """Validate and persist a retained diagnosis preview."""
    _owned_context(db, user.id, payload.farm_id, payload.crop_id)
    safe_token = Path(payload.image_token).name
    path = get_settings().uploads_dir / safe_token
    if safe_token != payload.image_token or not path.exists():
        raise HTTPException(400, "Uploaded image reference is invalid or expired.")
    diagnosis = CropDiagnosis(
        farmer_id=user.id, farm_id=payload.farm_id, crop_id=payload.crop_id,
        image_path=str(path), predicted_class=payload.predicted_class,
        display_name=payload.display_name, confidence=payload.confidence,
        severity=payload.severity, advisory=json.dumps(payload.advisory, ensure_ascii=False),
        model_version=payload.model_version,
    )
    db.add(diagnosis)
    db.flush()
    create_crop_alerts(db, diagnosis)
    db.commit()
    db.refresh(diagnosis)
    return diagnosis


@router.post("/save", response_model=DiagnosisOut, status_code=201)
def save_diagnosis(payload: DiagnosisSave, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return persist_diagnosis(payload, db, user)


@router.get("/history", response_model=list[DiagnosisOut])
def diagnosis_history(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(CropDiagnosis).where(CropDiagnosis.farmer_id == user.id).order_by(CropDiagnosis.created_at.desc())).all()


@router.get("/{diagnosis_id}", response_model=DiagnosisOut)
def diagnosis_detail(diagnosis_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    diagnosis = db.scalar(select(CropDiagnosis).where(CropDiagnosis.id == diagnosis_id, CropDiagnosis.farmer_id == user.id))
    if not diagnosis:
        raise HTTPException(404, "Diagnosis not found.")
    return diagnosis
