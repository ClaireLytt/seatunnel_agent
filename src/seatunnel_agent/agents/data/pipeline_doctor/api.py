"""REST API for the pipeline failure diagnosis agent — FastAPI router.

  POST /api/pipedoctor/diagnose — match failure signatures over run logs
  POST /api/pipedoctor/rundiff  — failed run vs known-good baseline run
  POST /api/pipedoctor/advice   — LLM advice on a diagnosis
  GET  /api/pipedoctor/health   — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since, require_dir
from seatunnel_agent.common.utils import normalize_lang

from .report import diagnosis_to_dict, render_markdown

router = APIRouter(prefix="/api/pipedoctor", tags=["pipeline_doctor"])

DEFAULT_PATTERNS = ("*.log", "*.log.*", "*.out", "*.err")


class DiagnoseRequest(BaseModel):
    dir: str | None = Field(None, description="Log directory (recursive)")
    text: str | None = Field(None, description="Inline log text to diagnose")
    patterns: list[str] | None = Field(
        None, description=f"File globs, default {list(DEFAULT_PATTERNS)}")
    top: int = Field(10, ge=1, le=50, description="Findings to include")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class DiagnoseResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


def _scan_input(dir_: str | None, text: str | None,
                patterns: list[str] | None, name: str):
    """One whitelisted dir-or-inline-text scan (shared by all endpoints)."""
    from seatunnel_agent.agents.data.log_inspect.clusterer import (
        scan_dir,
        scan_text,
    )

    if (dir_ or "").strip():
        target = require_dir(dir_, "PIPEDOCTOR_API_ALLOWED_DIRS")
        return scan_dir(target, patterns=tuple(patterns or DEFAULT_PATTERNS))
    return scan_text(text or "", name=name)


def _run_diagnosis(dir_: str | None, text: str | None,
                   patterns: list[str] | None):
    from .diagnoser import diagnose_report

    return diagnose_report(_scan_input(dir_, text, patterns, "<inline>"))


@router.post("/diagnose", response_model=DiagnoseResponse)
def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    start = time.time()
    if not (req.dir or "").strip() and not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'dir' or 'text'")
    lang = normalize_lang(req.lang)
    diag = _run_diagnosis(req.dir, req.text, req.patterns)
    return DiagnoseResponse(
        result=diagnosis_to_dict(diag, top=req.top),
        report=(render_markdown(diag, lang, top=req.top)
                if req.report else None),
        elapsed_ms=ms_since(start),
    )


class RunDiffRequest(BaseModel):
    dir: str | None = Field(None, description="Current (failed) run log dir")
    text: str | None = Field(None, description="Current run inline log text")
    baseline_dir: str | None = Field(
        None, description="Known-good baseline run log dir")
    baseline_text: str | None = Field(
        None, description="Baseline inline log text")
    patterns: list[str] | None = Field(
        None, description=f"File globs, default {list(DEFAULT_PATTERNS)}")
    top: int = Field(10, ge=1, le=50, description="Entries per section")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class RunDiffResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/rundiff", response_model=RunDiffResponse)
def rundiff(req: RunDiffRequest) -> RunDiffResponse:
    """Regression diff: clusters new/grown vs a known-good baseline."""
    from .report import render_diff_markdown
    from .rundiff import diff_reports

    start = time.time()
    if not (req.dir or "").strip() and not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'dir' or 'text'")
    if (not (req.baseline_dir or "").strip()
            and not (req.baseline_text or "").strip()):
        raise HTTPException(status_code=400,
                            detail="Provide 'baseline_dir' or 'baseline_text'")
    cur = _scan_input(req.dir, req.text, req.patterns, "<current>")
    base = _scan_input(req.baseline_dir, req.baseline_text, req.patterns,
                       "<baseline>")
    diff = diff_reports(cur, base)
    lang = normalize_lang(req.lang)
    return RunDiffResponse(
        result=diff.to_dict(),
        report=(render_diff_markdown(diff, lang, top=req.top)
                if req.report else None),
        elapsed_ms=ms_since(start),
    )


class AdviceRequest(BaseModel):
    dir: str | None = Field(None, description="Log directory (recursive)")
    text: str | None = Field(None, description="Inline log text to diagnose")
    patterns: list[str] | None = Field(None, description="File globs")
    top: int = Field(5, ge=1, le=20, description="Findings to advise on")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")


class AdviceResponse(BaseModel):
    advice: str
    elapsed_ms: int


@router.post("/advice", response_model=AdviceResponse)
def advice(req: AdviceRequest) -> AdviceResponse:
    """LLM advice on the diagnosis — requires an API key."""
    start = time.time()
    if not (req.dir or "").strip() and not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'dir' or 'text'")
    diag = _run_diagnosis(req.dir, req.text, req.patterns)
    if not diag.findings and not diag.unmatched:
        raise HTTPException(status_code=400,
                            detail="Nothing to advise on — no findings")
    try:
        from seatunnel_agent.common.config import load_settings

        settings = load_settings()
    except RuntimeError:
        raise HTTPException(status_code=400, detail="No API key configured")
    from .advisor import generate_advice

    lang = normalize_lang(req.lang)
    text = generate_advice(settings, diag, lang, top=req.top)
    return AdviceResponse(advice=text or "", elapsed_ms=ms_since(start))


add_health(router, "pipeline_doctor")
