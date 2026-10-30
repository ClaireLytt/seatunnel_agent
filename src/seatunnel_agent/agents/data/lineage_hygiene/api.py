"""REST API for the warehouse-hygiene agent — a ScanSpec on the shared seam.

  POST /api/hygiene/scan   — analyze inline SQL or a whitelisted directory
  GET  /api/hygiene/health — health check

The endpoint mechanics live in :mod:`seatunnel_agent.common.scan_api`;
this spec adds the agent's one extra request field (the orphan exemption
pattern list).
"""

from __future__ import annotations

from pydantic import Field

from seatunnel_agent.common.scan_api import ScanSpec, make_scan_router

from .analyzer import analyze_dir, analyze_sql_text
from .history import HygieneLogger
from .report import render_markdown

SPEC = ScanSpec(
    name="lineage_hygiene",
    prefix="/api/hygiene",
    whitelist_env="HYGIENE_API_ALLOWED_DIRS",
    error_code="hygiene_failed",
    analyze_dir=analyze_dir,
    analyze_sql=analyze_sql_text,
    render=render_markdown,
    to_dict=lambda result, lang: result.to_dict(),
    log_run=lambda result: HygieneLogger().log_run(result, source="api"),
    log_recent=lambda n: HygieneLogger().recent(n),
    extra_fields={
        "exempt": (list[str], Field(
            default_factory=list,
            description="fnmatch patterns of externally-read tables to "
                        "exempt from the orphan verdict")),
    },
)

router = make_scan_router(SPEC)
