"""CSV export of query results.

Default target is the user's Desktop with a timestamped filename
(PRD 6.9); a caller-supplied path overrides the default. Files are written
as UTF-8 with BOM so Excel renders Chinese headers correctly.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path


def default_desktop_dir() -> Path:
    desktop = Path.home() / "Desktop"
    return desktop if desktop.is_dir() else Path.home()


def _safe_stem(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", name)[:60] or "query_result"


def export_csv(
    columns: list[str],
    rows: list[tuple],
    path: str | None = None,
    name_hint: str = "query_result",
) -> str:
    """Write rows to CSV and return the absolute file path."""
    if path:
        target = Path(path)
        if target.is_dir() or not target.suffix:
            target.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target = target / f"{_safe_stem(name_hint)}_{timestamp}.csv"
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = default_desktop_dir() / f"{_safe_stem(name_hint)}_{timestamp}.csv"

    with open(target, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    return str(target.resolve())
