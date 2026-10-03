from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any


def truncate(text: str, max_chars: int = 3000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated]"


def find_latest_log(log_dir: str) -> str | None:
    log_path = Path(log_dir)
    if not log_path.is_dir():
        return None
    log_files = list(log_path.glob("*.log"))
    if not log_files:
        return None
    return str(max(log_files, key=lambda f: f.stat().st_mtime))


def safe_json(data: Any) -> str:
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return json.dumps({"error": "Failed to serialize result"})


def is_windows() -> bool:
    return platform.system() == "Windows"


def resolve_log_path(path: str, seatunnel_home: str) -> str:
    """If path is a directory, find the latest log in it.
    If path is 'auto', look in $SEATUNNEL_HOME/logs/."""
    if path == "auto":
        log_dir = str(Path(seatunnel_home) / "logs")
        found = find_latest_log(log_dir)
        if found:
            return found
        raise FileNotFoundError(
            f"No log files found in {log_dir}. "
            "Provide a specific log file path instead."
        )
    if os.path.isdir(path):
        found = find_latest_log(path)
        if found:
            return found
        raise FileNotFoundError(f"No log files found in {path}")
    return path


def cjk_font_family() -> str | None:
    """Name of an installed CJK-capable font for matplotlib text, or None.

    Matplotlib's default DejaVu Sans has no CJK glyphs, so Chinese chart
    titles/legends render as empty boxes unless a CJK font is set
    explicitly on those text elements."""
    try:
        from matplotlib import font_manager
    except ImportError:
        return None
    try:
        names = {f.name for f in font_manager.fontManager.ttflist}
    except Exception:  # noqa: BLE001 - a font cache problem must not break charts
        return None
    for cand in ("Microsoft YaHei", "SimHei", "PingFang SC",
                 "Hiragino Sans GB", "Noto Sans CJK SC",
                 "Source Han Sans SC", "WenQuanYi Micro Hei"):
        if cand in names:
            return cand
    return None
