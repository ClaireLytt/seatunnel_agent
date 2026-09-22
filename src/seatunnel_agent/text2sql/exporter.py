"""CSV export of query results.

Default target is the user's Desktop with a timestamped filename
(PRD 6.9); a caller-supplied path overrides the default. Files are written
as UTF-8 with BOM so Excel renders Chinese headers correctly.
"""

from __future__ import annotations

import csv
import os
import re
from datetime import datetime, timezone
from pathlib import Path

NOTO_SANS_SC_URL = (
    "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/"
    "SimplifiedChinese/NotoSansSC-Regular.otf"
)
FONT_CACHE_DIR = Path.home() / ".seatunnel-agent" / "fonts"
NOTO_FONT_PATH = FONT_CACHE_DIR / "NotoSansSC-Regular.otf"
_FONT_DOWNLOAD_TIMEOUT_S = 15


def download_noto_font(timeout: int = _FONT_DOWNLOAD_TIMEOUT_S) -> Path | None:
    """Download the Noto Sans SC font to the local cache. Returns the path or None."""
    try:
        FONT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        import urllib.request
        resp = urllib.request.urlopen(NOTO_SANS_SC_URL, timeout=timeout)  # noqa: S310
        with open(NOTO_FONT_PATH, "wb") as f:
            f.write(resp.read())
        return NOTO_FONT_PATH if NOTO_FONT_PATH.is_file() else None
    except Exception:
        return None


def default_desktop_dir() -> Path:
    override = os.getenv("EXPORT_DIR", "").strip()
    if override:
        p = Path(override)
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except OSError:
            pass
    desktop = Path.home() / "Desktop"
    return desktop if desktop.is_dir() else Path.home()


def safe_stem(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", name)[:60] or "query_result"


def _timestamped_name(name_hint: str, ext: str = "csv") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{safe_stem(name_hint)}_{ts}.{ext}"


def _resolve_target(path: str | None, name_hint: str, ext: str) -> Path:
    """Resolve the output file path: explicit file, directory, or default dir."""
    fname = _timestamped_name(name_hint, ext)
    if path:
        target = Path(path)
        if target.is_dir() or not target.suffix:
            target.mkdir(parents=True, exist_ok=True)
            return target / fname
        target.parent.mkdir(parents=True, exist_ok=True)
        return target
    return default_desktop_dir() / fname


def export_csv(
    columns: list[str],
    rows: list[tuple],
    path: str | None = None,
    name_hint: str = "query_result",
) -> str:
    """Write rows to CSV and return the absolute file path."""
    target = _resolve_target(path, name_hint, "csv")

    with open(target, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        ncols = len(columns)
        writer.writerow(columns)
        for r in rows:
            row = list(r)
            if len(row) < ncols:
                row.extend([None] * (ncols - len(row)))
            writer.writerow(row)
    return str(target.resolve())


def export_excel(
    columns: list[str],
    rows: list[tuple],
    path: str | None = None,
    name_hint: str = "query_result",
) -> str:
    """Write rows to an Excel .xlsx file and return the absolute path."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment
    except ImportError:
        raise RuntimeError(
            "openpyxl is required for Excel export. "
            "Install it with: pip install openpyxl"
        )

    target = _resolve_target(path, name_hint, "xlsx")

    wb = Workbook()
    ws = wb.active
    ws.title = "Query Result"

    bold = Font(bold=True)
    for ci, col_name in enumerate(columns, 1):
        cell = ws.cell(row=1, column=ci, value=col_name)
        cell.font = bold
        cell.alignment = Alignment(horizontal="center")

    for ri, row in enumerate(rows, 2):
        for ci in range(1, len(columns) + 1):
            val = row[ci - 1] if ci - 1 < len(row) else None
            ws.cell(row=ri, column=ci, value=val)

    for ci, col_name in enumerate(columns, 1):
        max_len = len(str(col_name))
        for row in rows[:100]:
            cell_len = len(str(row[ci - 1])) if ci - 1 < len(row) else 0
            max_len = max(max_len, cell_len)
        ws.column_dimensions[ws.cell(row=1, column=ci).column_letter].width = min(max_len + 4, 50)

    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"

    wb.save(target)
    return str(target.resolve())


def export_pdf(
    columns: list[str],
    rows: list[tuple],
    path: str | None = None,
    name_hint: str = "query_result",
    title: str = "Query Result Report",
) -> str:
    """Write rows to a PDF table and return the absolute path."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise RuntimeError(
            "fpdf2 is required for PDF export. "
            "Install it with: pip install fpdf2"
        )

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    target = _resolve_target(path, name_hint, "pdf")

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)

    _font_family = "Helvetica"
    if NOTO_FONT_PATH.is_file():
        pdf.add_font("NotoSansSC", "", str(NOTO_FONT_PATH), uni=True)
        _font_family = "NotoSansSC"
    else:
        import unicodedata
        has_cjk = any(
            unicodedata.category(ch).startswith("Lo")
            for col in columns for ch in str(col)
        )
        if has_cjk and download_noto_font() is not None:
            pdf.add_font("NotoSansSC", "", str(NOTO_FONT_PATH), uni=True)
            _font_family = "NotoSansSC"

    pdf.add_page()

    pdf.set_font(_font_family, "B" if _font_family == "Helvetica" else "", 14)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font(_font_family, "", 8)
    pdf.cell(0, 6, f"Generated: {ts}  |  Rows: {len(rows)}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    n_cols = len(columns)
    page_w = pdf.w - pdf.l_margin - pdf.r_margin
    col_w = page_w / max(n_cols, 1)

    pdf.set_font(_font_family, "B" if _font_family == "Helvetica" else "", 7)
    pdf.set_fill_color(220, 220, 220)
    for col_name in columns:
        pdf.cell(col_w, 6, str(col_name)[:20], border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font(_font_family, "", 7)
    for row in rows:
        for ci, val in enumerate(row):
            text = str(val) if val is not None else ""
            pdf.cell(col_w, 5, text[:25], border=1)
        for _ in range(max(0, n_cols - len(row))):
            pdf.cell(col_w, 5, "", border=1)
        pdf.ln()

    pdf.output(str(target))
    return str(target.resolve())
