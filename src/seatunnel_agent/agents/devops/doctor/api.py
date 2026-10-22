"""REST API for the environment doctor — FastAPI router.

  POST /api/doctor/diagnose  — LLM diagnosis (falls back to deterministic)
  GET  /api/doctor/checkup   — deterministic full check-up (no LLM)
  GET  /api/doctor/health    — health check
"""

from __future__ import annotations

import time

from fastapi import APIRouter
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since
from seatunnel_agent.common.utils import normalize_lang

from .engine import diagnose

router = APIRouter(prefix="/api/doctor", tags=["doctor"])


class DiagnoseRequest(BaseModel):
    complaint: str = Field(..., min_length=1,
                           description="Symptom description")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")


class DiagnoseResponse(BaseModel):
    reply: str
    deterministic: bool
    elapsed_ms: int


@router.post("/diagnose", response_model=DiagnoseResponse)
def do_diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    start = time.time()
    lang = normalize_lang(req.lang)
    try:
        from seatunnel_agent.common.config import llm_ready, load_settings

        settings = load_settings() if llm_ready() else None
    except Exception:
        settings = None
    result = diagnose(req.complaint, settings=settings, lang=lang)
    return DiagnoseResponse(
        reply=result.reply,
        deterministic=result.deterministic,
        elapsed_ms=ms_since(start),
    )


@router.get("/checkup", response_model=DiagnoseResponse)
def checkup(lang: str = "zh") -> DiagnoseResponse:
    """Deterministic full check-up — no LLM needed."""
    start = time.time()
    result = diagnose("checkup", settings=None, lang=normalize_lang(lang))
    return DiagnoseResponse(
        reply=result.reply,
        deterministic=result.deterministic,
        elapsed_ms=ms_since(start),
    )


add_health(router, "doctor")
