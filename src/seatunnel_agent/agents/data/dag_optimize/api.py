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

from .optimizer import diff_dags, optimize, parse_dag
from .report import render_diff_markdown, render_markdown

router = APIRouter(prefix="/api/dagopt", tags=["dag_optimize"])

_ENV = "DAGOPT_API_ALLOWED_DIRS"


class AnalyzeRequest(BaseModel):
    file: str | None = Field(
        None, description="Task DAG file (.json or text lines)")
    text: str | None = Field(None, description="Inline DAG definition")
    base_file: str | None = Field(
        None, description="Baseline DAG file — adds the change review")
    base_text: str | None = Field(None, description="Inline baseline DAG")
    deadline: float = Field(
        0.0, ge=0, description="Optional SLA duration to check against")
    llm: bool = Field(
        False, description="Also write a prioritized action plan via the "
                           "configured LLM (needs an API key)")
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
    base_raw = (_read_whitelisted(req.base_file or "")
                if (req.base_file or "").strip() else req.base_text or "")
    try:
        graph = parse_dag(text)
        result = optimize(graph, deadline=req.deadline)
        diff = (diff_dags(parse_dag(base_raw), graph)
                if base_raw.strip() else None)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # malformed JSON
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    lang = normalize_lang(req.lang)
    report = render_markdown(result, lang=lang) if req.report else None
    payload = result.to_dict()
    if diff is not None:
        payload["diff"] = diff.to_dict()
        if report is not None:
            report = render_diff_markdown(diff, lang=lang) + "\n" + report
    if req.llm:
        from . import advisor_llm
        from .i18n import tp

        try:
            plan = advisor_llm.action_plan(result, lang=lang)
        except Exception as exc:  # missing key, provider errors
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        payload["action_plan"] = plan
        if report is not None:
            report += f"\n\n### {tp(lang, 'rpt_action_plan')}\n{plan}\n"
    return AnalyzeResponse(result=payload, report=report,
                           elapsed_ms=ms_since(start))


add_health(router, "dag_optimize")
