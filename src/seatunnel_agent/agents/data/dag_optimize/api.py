"""REST API for the DAG optimizer agent — FastAPI router.

  POST /api/dagopt/analyze — redundant edges + waves + critical path
  GET  /api/dagopt/health  — health check
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since, require_dir
from seatunnel_agent.common.utils import normalize_lang

from .optimizer import optimize, parse_dag
from .report import render_markdown

router = APIRouter(prefix="/api/dagopt", tags=["dag_optimize"])

_ENV = "DAGOPT_API_ALLOWED_DIRS"


class AnalyzeRequest(BaseModel):
    file: str | None = Field(
        None, description="Task DAG file (.json or text lines)")
    text: str | None = Field(None, description="Inline DAG definition")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class AnalyzeResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


def _read_whitelisted(raw: str) -> str:
    path = Path(raw.strip())
    require_dir(str(path.parent), _ENV)
    if not path.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


@router.post("/analyze", response_model=AnalyzeResponse)
def run_analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    start = time.time()
    if not (req.file or "").strip() and not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'file' or 'text'")
    text = (_read_whitelisted(req.file or "") if (req.file or "").strip()
            else req.text or "")
    try:
        result = optimize(parse_dag(text))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # malformed JSON
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    lang = normalize_lang(req.lang)
    report = render_markdown(result, lang=lang) if req.report else None
    return AnalyzeResponse(result=result.to_dict(), report=report,
                           elapsed_ms=ms_since(start))


add_health(router, "dag_optimize")
