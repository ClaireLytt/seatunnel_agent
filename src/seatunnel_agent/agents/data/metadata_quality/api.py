"""REST API for the metadata-quality agent — a ScanSpec on the shared seam.

  POST /api/metaquality/scan   — check inline SQL or a whitelisted directory
  GET  /api/metaquality/health — health check

The endpoint mechanics (whitelist, error envelope, timing, history record,
response envelope) live in :mod:`seatunnel_agent.common.scan_api`.
"""

from __future__ import annotations

from seatunnel_agent.common.scan_api import ScanSpec, make_scan_router

from .checker import check_dir, check_sql_text
from .history import MetaQualityLogger
from .report import render_markdown

SPEC = ScanSpec(
    name="metadata_quality",
    prefix="/api/metaquality",
    whitelist_env="METAQUALITY_API_ALLOWED_DIRS",
    error_code="metaquality_failed",
    analyze_dir=check_dir,
    analyze_sql=check_sql_text,
    render=render_markdown,
    to_dict=lambda result, lang: result.to_dict(),
    log_run=lambda result: MetaQualityLogger().log_run(result, source="api"),
)

router = make_scan_router(SPEC)
