"""REST API for the migration-guard agent — a ScanSpec on the shared seam.

  POST /api/ddlguard/scan   — scan inline SQL or a whitelisted directory
  GET  /api/ddlguard/health — health check

The rollback script rides inside the result payload (``undo_sql``).
"""

from __future__ import annotations

from seatunnel_agent.common.scan_api import ScanSpec, make_scan_router

from .guard import scan_dir, scan_sql_text
from .report import render_markdown

SPEC = ScanSpec(
    name="ddl_guard",
    prefix="/api/ddlguard",
    whitelist_env="DDLGUARD_API_ALLOWED_DIRS",
    error_code="ddlguard_failed",
    analyze_dir=scan_dir,
    analyze_sql=scan_sql_text,
    render=render_markdown,
    to_dict=lambda result, lang: result.to_dict(),
)

router = make_scan_router(SPEC)
