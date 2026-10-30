"""REST API for the backfill planner agent — FastAPI router.

  POST /api/backfill/plan   — gaps + cascade + topological batches
  GET  /api/backfill/health — health check
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since, require_dir
from seatunnel_agent.common.utils import normalize_lang

from .planner import plan, plan_to_dict
from .report import render_markdown

router = APIRouter(prefix="/api/backfill", tags=["backfill"])

_ENV = "BACKFILL_API_ALLOWED_DIRS"


class PlanRequest(BaseModel):
    file: str | None = Field(
        None, description="Update-event inventory file (.json/.csv)")
    text: str | None = Field(None, description="Inline JSON/CSV inventory")
    rules_file: str | None = Field(
        None, description="Freshness rules file (JSON)")
    rules_text: str | None = Field(None, description="Inline rules JSON")
    sql_dir: str | None = Field(
        None, description="Lineage SQL directory (recursive *.sql)")
    now: str | None = Field(
        None, description="Evaluation time, ISO timestamp "
                          "(default: latest update seen)")
    since: str | None = Field(
        None, description="Only plan slots at or after this timestamp")
    cmd: str = Field("", description="Command template with {table}/{date}")
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
    from seatunnel_agent.agents.data.data_freshness import (
        parse_events,
        parse_rules,
    )
    from seatunnel_agent.agents.data.data_lineage.loaders import from_sql_dir

    start = time.time()
    if not (req.file or "").strip() and not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'file' or 'text'")
    text = (_read_whitelisted(req.file) if (req.file or "").strip()
            else req.text or "")
    rules_text = (_read_whitelisted(req.rules_file)
                  if (req.rules_file or "").strip() else req.rules_text or "")
    graph = None
    warnings: list[str] = []
    if (req.sql_dir or "").strip():
        sql_dir = require_dir(req.sql_dir, _ENV)
        graph, warnings = from_sql_dir(sql_dir)
    try:
        result = plan(parse_events(text), parse_rules(rules_text),
                      graph=graph,
                      now=(req.now or "").strip() or None,
                      since=(req.since or "").strip() or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    result.warnings.extend(warnings)
    lang = normalize_lang(req.lang)
    return PlanResponse(
        result=plan_to_dict(result),
        report=(render_markdown(result, lang, cmd_template=req.cmd)
                if req.report else None),
        elapsed_ms=ms_since(start),
    )


add_health(router, "backfill")
