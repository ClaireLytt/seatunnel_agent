"""REST API for the migration assessor agent — FastAPI router.

  POST /api/pipemigrate/assess — per-job target, effort and risks
  GET  /api/pipemigrate/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since, require_dir
from seatunnel_agent.common.utils import normalize_lang

from .assessor import assess_dir, assess_text
from .report import render_markdown

router = APIRouter(prefix="/api/pipemigrate", tags=["pipeline_migrate"])

_ENV = "PIPEMIGRATE_API_ALLOWED_DIRS"


class AssessRequest(BaseModel):
    dir: str | None = Field(
        None, description="Legacy scripts directory (recursive)")
    text: str | None = Field(None, description="One inline script")
    name: str = Field("pasted.sql", description="Name for the inline script")
    llm: bool = Field(
        False, description="Also ask the configured LLM for rewrite advice "
                           "on the riskiest jobs (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class AssessResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/assess", response_model=AssessResponse)
def run_assess(req: AssessRequest) -> AssessResponse:
    start = time.time()
    if not (req.dir or "").strip() and not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'dir' or 'text'")
    try:
        if (req.dir or "").strip():
            result = assess_dir(require_dir(req.dir or "", _ENV))
        else:
            result = assess_text(req.name, req.text or "")
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    lang = normalize_lang(req.lang)
    report = render_markdown(result, lang=lang) if req.report else None
    payload = result.to_dict()
    if req.llm:
        try:
            advice = _collect_advice(result, req, lang)
        except Exception as exc:  # missing key, provider errors
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        payload["llm_advice"] = [{"job": j, "advice": a} for j, a in advice]
        if report is not None and advice:
            report += "\n\n" + _advice_markdown(advice, lang)
    return AssessResponse(result=payload, report=report,
                          elapsed_ms=ms_since(start))


def _collect_advice(result: Any, req: AssessRequest,
                    lang: str) -> list[tuple[str, str]]:
    from pathlib import Path

    from .advisor_llm import advice_for_jobs

    if (req.dir or "").strip():
        root = Path(req.dir.strip() if req.dir else "")
        scripts = {j.job: (root / j.job).read_text(encoding="utf-8",
                                                   errors="replace")
                   for j in result.jobs if j.risks and (root / j.job).is_file()}
    else:
        scripts = {req.name: req.text or ""}
    return advice_for_jobs(result.jobs, scripts, lang=lang)


def _advice_markdown(advice: list[tuple[str, str]], lang: str) -> str:
    from .i18n import tp

    lines = [f"### {tp(lang, 'rpt_llm_advice')}"]
    for job, text in advice:
        lines.append(f"**`{job}`**")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


add_health(router, "pipeline_migrate")
