"""REST API for the React Config Migrate page (/api/config_migrate).

Ticket 01 surface: single-text migration. Stateless — each request is a
pure call into the rule-based migrator; deliberately imports the
Gradio-free modules only (migrator/report), never ``ui.py``.
"""

from __future__ import annotations

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
from seatunnel_agent.common.api_guard import check_path_allowed, require_dir

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
    jobs_dir = require_dir(jobs_dir, "CONFIG_MIGRATE_API_ALLOWED_DIRS")
    out_dir = req.out_dir.strip() or None
    if out_dir:  # write target stays under the same whitelist
        check_path_allowed(out_dir, "CONFIG_MIGRATE_API_ALLOWED_DIRS")
    try:
        res = migrate_dir(jobs_dir, out_dir=out_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "stats": res.counts(),
        "report": render_batch_markdown(res, req.lang),
    }
