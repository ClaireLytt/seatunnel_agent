"""REST API for issue triage — FastAPI router.

  POST /api/triage/run    — triage an inline issue (optional inline history)
  GET  /api/triage/health — health check
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since

from .engine import load_issues, triage
from .report import normalize_lang, render_markdown

router = APIRouter(prefix="/api/triage", tags=["issue_triage"])

# Bundled demo history — same file the legacy Gradio page used (ui.py _DEMO).
_DEMO = (Path(__file__).resolve().parents[5] / "examples" / "triage_demo"
         / "issues.jsonl")


class TriageRequest(BaseModel):
    title: str = Field(..., min_length=1)
    body: str = Field("", description="Issue body")
    issues: list[dict[str, Any]] | None = Field(
        None,
        description="History issues [{number,title,body,labels}] for dedupe;"
                    " omit for the bundled demo history, [] for none")
    lang: str = "zh"
    report: bool = Field(False, description="Include the markdown report")


class TriageResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/run", response_model=TriageResponse)
def run(req: TriageRequest) -> TriageResponse:
    start = time.time()
    from dotenv import load_dotenv

    from seatunnel_agent.common import settings_store
    from seatunnel_agent.common.config import load_settings
    load_dotenv()
    settings_store.apply_to_env()
    try:
        settings = load_settings()
    except RuntimeError as exc:  # no API key
        raise HTTPException(status_code=503, detail=str(exc))
    if req.issues is None:
        issues = load_issues(_DEMO) if _DEMO.is_file() else []
    else:
        issues = req.issues
    try:
        result = triage(req.title, req.body, settings, issues=issues,
                        repo_dir=None)
    except Exception as exc:
        raise HTTPException(status_code=502,
                            detail=f"{type(exc).__name__}: {exc}")
    return TriageResponse(
        result=result.to_dict(),
        report=(render_markdown(result, normalize_lang(req.lang))
                if req.report else None),
        elapsed_ms=ms_since(start))


add_health(router, "issue_triage")
