"""REST API for the metric consistency checker — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Endpoints (deterministic — nothing executed):

  POST /api/metricdiff/check  — analyze a whitelisted SQL directory
  GET  /api/metricdiff/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_agent_router

from . import differ
from .report import render_markdown, report_to_dict

# Re-export so existing monkeypatches (tests) can replace the name.
check_sql_dir = differ.check_sql_dir


class MetricDiffRequest(BaseModel):
    sql_dir: str = Field(..., min_length=1,
                         description="Directory scanned recursively for *.sql")
    dialect: str = Field("hive", description="SQL dialect for parsing")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _domain(path: str, *, dialect: str = "hive"):
    """Late-bound wrapper so monkeypatching ``check_sql_dir`` works."""
    import sys
    mod = sys.modules[__name__]
    return mod.check_sql_dir(path, dialect=dialect)


router = make_agent_router(
    prefix="/api/metricdiff",
    tags=["metric_diff"],
    domain_fn=_domain,
    request_model=MetricDiffRequest,
    allowed_dirs_env="METRICDIFF_API_ALLOWED_DIRS",
    health_name="metric_diff",
    report_to_dict=report_to_dict,
    render_markdown=render_markdown,
)
