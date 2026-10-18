"""REST API for the React Config Migrate page (/api/config_migrate).

Ticket 01 surface: single-text migration. Stateless — each request is a
pure call into the rule-based migrator; deliberately imports the
Gradio-free modules only (migrator/report), never ``ui.py``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from seatunnel_agent.agents.data.config_migrate.migrator import migrate_text
from seatunnel_agent.agents.data.config_migrate.report import (
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
