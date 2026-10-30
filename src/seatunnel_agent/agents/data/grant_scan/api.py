"""REST API for the grant-surface agent — a ScanSpec on the shared seam.

  POST /api/grants/scan   — scan inline SQL or a whitelisted directory
  GET  /api/grants/health — health check
"""

from __future__ import annotations

from seatunnel_agent.common.scan_api import ScanSpec, make_scan_router

from .history import GrantsLogger
from .report import render_markdown
from .scanner import scan_dir, scan_sql_text

SPEC = ScanSpec(
    name="grant_scan",
    prefix="/api/grants",
    whitelist_env="GRANTS_API_ALLOWED_DIRS",
    error_code="grants_failed",
    analyze_dir=scan_dir,
    analyze_sql=scan_sql_text,
    render=render_markdown,
    to_dict=lambda result, lang: result.to_dict(),
    log_run=lambda result: GrantsLogger().log_run(result, source="api"),
    log_recent=lambda n: GrantsLogger().recent(n),
)

router = make_scan_router(SPEC)
