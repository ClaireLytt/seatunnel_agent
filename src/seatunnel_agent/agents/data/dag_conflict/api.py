"""REST API for the DAG conflict detector — FastAPI router.

  POST /api/dagconflict/simulate — windows, write conflicts, suggestion
  GET  /api/dagconflict/health   — health check
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .conflictor import parse_scenario, place, simulate
from .report import render_markdown, render_place

_ENV = "DAGCONFLICT_API_ALLOWED_DIRS"


class SimulateRequest(BaseModel):
    file: str | None = Field(None, description="Scenario JSON file")
    text: str | None = Field(None, description="Inline scenario JSON")
    place: str = Field(
        "", description="Admission check: sweep candidate start offsets "
                        "for this DAG and report the best placement")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: SimulateRequest, resolve):
    scenario = parse_scenario(resolve(req.file, req.text,
                                      "'file' or 'text'"))
    return scenario, simulate(scenario)


def _post(req: SimulateRequest, result, payload, lang: str) -> list[str]:
    scenario, _ = result
    if not req.place.strip():
        return []
    try:
        placement = place(scenario, req.place.strip())
    except ValueError as exc:  # unknown dag
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload["placement"] = placement
    return [render_place(placement, lang=lang)]


router = make_text_router(
    prefix="/api/dagconflict", tags=["dag_conflict"],
    endpoint="simulate", request_model=SimulateRequest,
    health_name="dag_conflict", env_var=_ENV,
    core=_core,
    to_payload=lambda result: result[1].to_dict(),
    render=lambda result, req, lang: render_markdown(result[1], lang=lang),
    post=_post,
)
