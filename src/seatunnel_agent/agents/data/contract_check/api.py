"""REST API for the data-contract agent — a ScanSpec on the shared seam.

  POST /api/contract/scan   — check inline SQL or a whitelisted directory
                              against a YAML contract (extra field)
  GET  /api/contract/health — health check
"""

from __future__ import annotations

from pydantic import Field

from seatunnel_agent.common.scan_api import ScanSpec, make_scan_router

from .checker import check_dir, check_sql_text
from .report import render_markdown

SPEC = ScanSpec(
    name="contract_check",
    prefix="/api/contract",
    whitelist_env="CONTRACT_API_ALLOWED_DIRS",
    error_code="contract_failed",
    analyze_dir=check_dir,
    analyze_sql=check_sql_text,
    render=render_markdown,
    to_dict=lambda result, lang: result.to_dict(),
    extra_fields={
        "contract": (str, Field(
            ...,
            description="YAML contract: tables with declared columns/types, "
                        "comment requirements and partition keys")),
    },
)

router = make_scan_router(SPEC)
