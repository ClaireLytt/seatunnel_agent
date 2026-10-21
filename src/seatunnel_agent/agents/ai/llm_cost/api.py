"""REST API for LLM cost observability — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Read-only: aggregates the local usage log, never calls an LLM.

  GET /api/llmcost/summary — cost/usage summary for the last N days
  GET /api/llmcost/prices  — the merged price table (override wins)
  GET /api/llmcost/health  — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from seatunnel_agent.common.api_guard import add_health, ms_since
from seatunnel_agent.common.utils import normalize_lang

from .aggregate import check_budget, summarize_cost
from .pricing import merged_prices, override_path
from .report import render_markdown

router = APIRouter(prefix="/api/llmcost", tags=["llm_cost"])


class SummaryResponse(BaseModel):
    summary: dict[str, Any]
    report: str | None = None
    over_budget: bool | None = None
    elapsed_ms: int


@router.get("/summary", response_model=SummaryResponse)
def summary(days: int = Query(30, ge=1, le=36500),
            budget: float | None = Query(None, ge=0),
            lang: str = "zh",
            report: bool = False) -> SummaryResponse:
    start = time.time()
    try:
        s = summarize_cost(days)
    except ValueError as exc:  # malformed pricing override
        raise HTTPException(status_code=400, detail=str(exc))
    return SummaryResponse(
        summary=s,
        report=render_markdown(s, normalize_lang(lang)) if report else None,
        over_budget=check_budget(s, budget) if budget is not None else None,
        elapsed_ms=ms_since(start),
    )


@router.get("/prices")
def prices() -> dict[str, Any]:
    """Merged price table (override entries first) — backs the React
    page's price accordion."""
    try:
        entries = merged_prices()
    except ValueError as exc:  # malformed pricing override
        raise HTTPException(status_code=400, detail=str(exc))
    return {"prices": [{"prefix": e.prefix, "input_usd": e.input_usd,
                        "output_usd": e.output_usd, "source": e.source}
                       for e in entries],
            "override_path": str(override_path())}


add_health(router, "llm_cost")
