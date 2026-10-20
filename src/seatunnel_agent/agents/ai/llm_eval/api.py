"""REST API for LLM eval — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Suites are passed inline (YAML text) — the API never reads arbitrary paths.

  POST /api/llmeval/run      — run an inline suite
  POST /api/llmeval/validate — parse-only suite check (never calls the LLM)
  GET  /api/llmeval/demo     — the bundled demo suite's YAML text
  GET  /api/llmeval/history  — recent run scores (for trend charts)
  GET  /api/llmeval/health   — health check
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since

from .baseline import RunLogger, compare
from .report import normalize_lang, render_markdown
from .runner import run_suite
from .suite import parse_suite

router = APIRouter(prefix="/api/llmeval", tags=["llm_eval"])


class RunRequest(BaseModel):
    suite_yaml: str = Field(..., min_length=1, description="Suite as YAML text")
    judge: bool = Field(False, description="Also run advisory judge checks")
    lang: str = "zh"
    report: bool = Field(False, description="Include the markdown report")


class RunResponse(BaseModel):
    result: dict[str, Any]
    regression: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/run", response_model=RunResponse)
def run(req: RunRequest) -> RunResponse:
    start = time.time()
    try:
        suite = parse_suite(req.suite_yaml)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    baseline = RunLogger().last_run(suite.name)  # BEFORE run_suite logs its own
    try:
        result = run_suite(suite, judge=req.judge)
    except RuntimeError as exc:  # e.g. API key not configured
        raise HTTPException(status_code=503, detail=str(exc))
    regression = compare(result, baseline)
    return RunResponse(
        result=result.to_dict(),
        regression=regression,
        report=(render_markdown(result, normalize_lang(req.lang), regression)
                if req.report else None),
        elapsed_ms=ms_since(start),
    )


class ValidateRequest(BaseModel):
    suite_yaml: str = Field(..., min_length=1, description="Suite as YAML text")


@router.post("/validate")
def validate(req: ValidateRequest) -> dict[str, Any]:
    """Parse-only feedback loop — never calls the LLM.  Message wording
    (valid/empty) is composed by the client from its i18n strings."""
    try:
        suite = parse_suite(req.suite_yaml)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "cases": len(suite.cases),
            "agents": sorted({c.agent for c in suite.cases})}


_DEMO_SUITE = (Path(__file__).resolve().parents[5] / "examples"
               / "llmeval_demo" / "text2sql_golden.yaml")


@router.get("/demo")
def demo() -> dict[str, str]:
    try:
        return {"text": _DEMO_SUITE.read_text(encoding="utf-8")}
    except OSError:
        return {"text": "suite: demo\ncases: []\n"}


@router.get("/history")
def history(suite: str | None = None,
            n: int = Query(50, ge=1, le=1000)) -> dict[str, Any]:
    return {"runs": RunLogger().recent(n=n, suite=suite)}


add_health(router, "llm_eval")
