# -*- coding: utf-8 -*-
"""Secret / credential scanner — naming patterns × entropy over code & config.

Deterministic, offline, never echoes a full secret (masked previews only).
No database, no LLM.
"""

from .report import render_markdown
from .scanner import (
    Finding,
    ScanConfig,
    ScanResult,
    check_fail,
    load_config,
    mask,
    scan_dir,
    scan_paths,
    scan_text,
)

__all__ = [
    "Finding",
    "ScanConfig",
    "ScanResult",
    "check_fail",
    "load_config",
    "mask",
    "render_markdown",
    "scan_dir",
    "scan_paths",
    "scan_text",
]
