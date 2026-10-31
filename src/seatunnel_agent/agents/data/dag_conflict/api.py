"""REST API for the DAG conflict detector — FastAPI router.

  POST /api/dagconflict/simulate — windows, write conflicts, suggestion
  GET  /api/dagconflict/health   — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import (
    add_health,
    ms_since,
    resolve_file_or_text,
)
from seatunnel_agent.common.utils import normalize_lang

from .conflictor import parse_scenario, place, simulate
from .report import render_markdown, render_place

router = APIRouter(prefix="/api/dagconflict", tags=["dag_conflict"])

_ENV = "DAGCONFLICT_API_ALLOWED_DIRS"


class SimulateRequest(BaseModel):
    file: str | None = Field(None, description="Scenario JSON file")
    text: str | None = Field(None, description="Inline scenario JSON")
    place: str = Field(
        "", description="Admission check: sweep candidate start offsets "
                        "for this DAG and report the best placement")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class SimulateResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/simulate", response_model=SimulateResponse)
def run_simulate(req: SimulateRequest) -> SimulateResponse:
    start = time.time()
    text = resolve_file_or_text(req.file, req.text, _ENV)
    try:
        scenario = parse_scenario(text)
        result = simulate(scenario)
    except Exception as exc:  # bad input, malformed JSON
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    lang = normalize_lang(req.lang)
    report = render_markdown(result, lang=lang) if req.report else None
    payload = result.to_dict()
    if req.place.strip():
        try:
            placement = place(scenario, req.place.strip())
        except ValueError as exc:  # unknown dag
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload["placement"] = placement
        if report is not None:
            report += "\n\n" + render_place(placement, lang=lang)
    return SimulateResponse(result=payload, report=report,
                            elapsed_ms=ms_since(start))


add_health(router, "dag_conflict")
