"""REST API for the rerun planner agent — FastAPI router.

  POST /api/rerun/plan   — minimal rerun set in topological batches
  GET  /api/rerun/health — health check
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since, require_dir
from seatunnel_agent.common.utils import normalize_lang

from .planner import parse_dag, parse_statuses, plan_rerun
from .report import render_markdown

router = APIRouter(prefix="/api/rerun", tags=["rerun_plan"])

_ENV = "RERUN_API_ALLOWED_DIRS"


class PlanRequest(BaseModel):
    file: str | None = Field(
        None, description="Task DAG file (.json or text lines)")
    text: str | None = Field(None, description="Inline DAG definition")
    failed: str = Field("", description="Failed task names, comma-separated")
    succeeded: str = Field(
        "", description="Already-succeeded task names, comma-separated")
    statuses: str = Field(
        "", description="Scheduler status export: {'task':'state'} JSON or "
                        "task=state lines (overrides failed/succeeded)")
    cmd: str = Field("", description="Command template with {task}")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class PlanResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


def _read_whitelisted(raw: str) -> str:
    path = Path(raw.strip())
    require_dir(str(path.parent), _ENV)
    if not path.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


@router.post("/plan", response_model=PlanResponse)
def run_plan(req: PlanRequest) -> PlanResponse:
    start = time.time()
    if not (req.file or "").strip() and not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'file' or 'text'")
    if not req.failed.strip() and not req.statuses.strip():
        raise HTTPException(status_code=400,
                            detail="Provide 'failed' or 'statuses'")
    text = (_read_whitelisted(req.file or "") if (req.file or "").strip()
            else req.text or "")
    try:
        failed: str | list[str] = req.failed
        succeeded: str | list[str] = req.succeeded
        if req.statuses.strip():
            failed, succeeded = parse_statuses(req.statuses)
        result = plan_rerun(parse_dag(text), failed, succeeded)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # malformed JSON
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    lang = normalize_lang(req.lang)
    report = (render_markdown(result, lang=lang, cmd_template=req.cmd)
              if req.report else None)
    return PlanResponse(result=result.to_dict(), report=report,
                        elapsed_ms=ms_since(start))


add_health(router, "rerun_plan")
