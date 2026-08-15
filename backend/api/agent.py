"""Natural-language agent API backed by LangGraph and local Ollama."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from backend.agent import AgentService, get_agent_service
from backend.api.deps import bearer, current_user
from backend.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["Agentic AI"])


class AgentQuery(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    thread_id: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class AgentResponse(BaseModel):
    answer: str
    thread_id: str
    model: str
    tool_calls: list[dict[str, Any]]


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
        result = service.run(payload.query, credentials.credentials, user.id, payload.thread_id)
    except Exception:
        logger.exception("Agent run failed for user=%s", user.id)
        raise HTTPException(
            503,
            f"The local AI agent is unavailable. Start Ollama and run: ollama pull {service.settings.ollama_model}",
        )
    return AgentResponse(
        answer=result.answer,
        thread_id=result.thread_id,
        model=result.model,
        tool_calls=result.tool_calls,
    )
