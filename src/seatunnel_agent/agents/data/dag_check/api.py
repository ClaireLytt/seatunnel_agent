"""REST API for the DAG health checker — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Endpoints (deterministic — nothing executed):

  POST /api/dagcheck/check  — analyze a whitelisted SQL directory
  GET  /api/dagcheck/health — health check
"""

from __future__ import annotations

import contextvars

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_agent_router

from .checker import check_sql_dir
from .report import render_markdown, report_to_dict

# Re-export so existing monkeypatches (tests) can replace the name.
_check_sql_dir = check_sql_dir

# Thread the optional seatunnel_dir through a context-var so the
# factory's ``domain_fn(path, dialect=)`` call-site needs no change.
_seatunnel_dir_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_seatunnel_dir_ctx", default=None,
)


class DagCheckRequest(BaseModel):
    sql_dir: str = Field(..., min_length=1,
                         description="Directory scanned recursively for *.sql")
    seatunnel_dir: str | None = Field(
        None, description="Optional SeaTunnel config directory to merge")
    dialect: str = Field("hive", description="SQL dialect for parsing")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _pre_check(req: DagCheckRequest) -> None:
    """Validate and stash seatunnel_dir before the domain call."""
    from pathlib import Path

    from fastapi import HTTPException

    from seatunnel_agent.common.api_guard import check_path_allowed

    st_dir = (req.seatunnel_dir or "").strip() or None
    if st_dir:
        check_path_allowed(st_dir, "DAGCHECK_API_ALLOWED_DIRS")
        if not Path(st_dir).is_dir():
            raise HTTPException(
                status_code=400,
                detail={"code": "bad_dir", "path": st_dir},
            )
    _seatunnel_dir_ctx.set(st_dir)


def _domain(path: str, *, dialect: str = "hive"):
    """Late-bound wrapper so monkeypatching ``_check_sql_dir`` works."""
    import sys

    mod = sys.modules[__name__]
    return mod._check_sql_dir(
        path, dialect=dialect, seatunnel_dir=_seatunnel_dir_ctx.get(),
    )


router = make_agent_router(
    prefix="/api/dagcheck",
    tags=["dag_check"],
    domain_fn=_domain,
    request_model=DagCheckRequest,
    allowed_dirs_env="DAGCHECK_API_ALLOWED_DIRS",
    health_name="dag_check",
    report_to_dict=report_to_dict,
    render_markdown=render_markdown,
    pre_check=_pre_check,
)
