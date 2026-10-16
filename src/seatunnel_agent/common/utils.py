from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def normalize_lang(lang: str | None) -> str:
    """Normalize any language hint to the two supported codes: en / zh."""
    return "en" if (lang or "").strip().lower().startswith("en") else "zh"


def collect_sql_files(directory: str | Path) -> list[Path]:
    """All *.sql files under *directory*, recursively, sorted."""
    return sorted(p for p in Path(directory).rglob("*.sql") if p.is_file())


def make_lookup(i18n: dict[str, dict[str, str]]):
    """Build a ``tp(lang, key)`` lookup over an EN/ZH string table.

    Falls back to the zh entry, then to the key itself — the shared
    behaviour of every module-level i18n table in this package."""
    def tp(lang: str, key: str) -> str:
        lang = normalize_lang(lang)
        return i18n.get(lang, {}).get(key) or i18n["zh"].get(key, key)
    return tp


def read_json_list(path: Path) -> list[Any]:
    """Read a JSON file expected to hold a list; missing/corrupt/non-list → []."""
    try:
        return read_json_list_strict(path)
    except ValueError:
        return []


def read_json_list_strict(path: Path) -> list[Any]:
    """Like :func:`read_json_list`, but distinguishes "missing file" from
    "file exists yet cannot be read as a JSON list": the former returns [],
    the latter raises ValueError. Use before a read-modify-write so a corrupt
    file is never silently overwritten with an empty list."""
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Cannot read JSON list from {path}: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(
            f"Cannot read JSON list from {path}: top-level value is not a list"
        )
    return data


def write_json_atomic(path: Path, data: Any) -> None:
    """Write JSON atomically: tempfile in the target's directory + os.replace,
    so readers never observe a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), suffix=".tmp", prefix=path.name,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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
    except Exception:
        return None
    for cand in ("Microsoft YaHei", "SimHei", "PingFang SC",
                 "Hiragino Sans GB", "Noto Sans CJK SC",
                 "Source Han Sans SC", "WenQuanYi Micro Hei"):
        if cand in names:
            return cand
    return None
