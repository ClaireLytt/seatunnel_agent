"""REST API for the React Config Migrate page (/api/config_migrate).

Ticket 01 surface: single-text migration. Stateless — each request is a
pure call into the rule-based migrator; deliberately imports the
Gradio-free modules only (migrator/report), never ``ui.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from seatunnel_agent.agents.data.config_migrate.migrator import (
    migrate_dir,
    migrate_text,
)
from seatunnel_agent.agents.data.config_migrate.report import (
    render_batch_markdown,
    render_migrate_markdown,
)

router = APIRouter(prefix="/api/config_migrate", tags=["config_migrate"])


class MigrateRequest(BaseModel):
    text: str
    lang: str = "en"


@router.post("/migrate")
def migrate(req: MigrateRequest) -> dict[str, Any]:
    """Migrate one DataX job JSON / sqoop command to SeaTunnel HOCON."""
    if not req.text.strip():
        raise HTTPException(status_code=422, detail="empty input")
    res = migrate_text(req.text)
    return {
        "ok": res.ok,
        "source_kind": res.source_kind,
        "conf": res.output_conf,
        "report": render_migrate_markdown(res, req.lang),
    }


class BatchRequest(BaseModel):
    jobs_dir: str
    out_dir: str = ""
    lang: str = "en"


@router.post("/batch")
def batch(req: BatchRequest) -> dict[str, Any]:
    """Migrate every DataX/sqoop job under a server-side directory.

    Paths keep the legacy Gradio semantics: they name directories on the
    machine running the hub, not browser uploads.
    """
    jobs_dir = req.jobs_dir.strip()
    if not jobs_dir:
        raise HTTPException(status_code=422, detail="empty jobs_dir")
    if not Path(jobs_dir).is_dir():
        raise HTTPException(status_code=404,
                            detail=f"not a directory: {jobs_dir}")
    try:
        res = migrate_dir(jobs_dir, out_dir=req.out_dir.strip() or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "stats": res.counts(),
        "report": render_batch_markdown(res, req.lang),
    }
