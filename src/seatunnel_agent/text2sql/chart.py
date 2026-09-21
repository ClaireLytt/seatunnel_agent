"""Auto-detect chart type from query results and build matplotlib figures."""

from __future__ import annotations

import base64
import io
import re
import threading
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


_cjk_font_configured = False
_cjk_font_lock = threading.Lock()


def _configure_cjk_font() -> None:
    """Set matplotlib to use a CJK-capable font for Chinese labels."""
    global _cjk_font_configured
    if _cjk_font_configured:
        return
    with _cjk_font_lock:
        if _cjk_font_configured:
            return
        _cjk_font_configured = True
    import matplotlib.font_manager as fm
    from pathlib import Path

    for name in ("Microsoft YaHei", "SimHei", "PingFang SC", "Noto Sans SC"):
        if any(name.lower() in f.name.lower() for f in fm.fontManager.ttflist):
            plt.rcParams["font.sans-serif"] = [name] + plt.rcParams.get(
                "font.sans-serif", []
            )
            plt.rcParams["axes.unicode_minus"] = False
            return

    noto = Path.home() / ".seatunnel-agent" / "fonts" / "NotoSansSC-Regular.otf"
    if noto.is_file():
        fm.fontManager.addfont(str(noto))
        plt.rcParams["font.sans-serif"] = ["Noto Sans SC"] + plt.rcParams.get(
            "font.sans-serif", []
        )
        plt.rcParams["axes.unicode_minus"] = False
        return

    def _download_font():
        try:
            noto.parent.mkdir(parents=True, exist_ok=True)
            import urllib.request
            _url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansSC-Regular.otf"
            resp = urllib.request.urlopen(_url, timeout=15)  # noqa: S310
            with open(noto, "wb") as _f:
                _f.write(resp.read())
            if noto.is_file():
                fm.fontManager.addfont(str(noto))
                plt.rcParams["font.sans-serif"] = ["Noto Sans SC"] + plt.rcParams.get(
                    "font.sans-serif", []
                )
                plt.rcParams["axes.unicode_minus"] = False
        except Exception:
            pass

    threading.Thread(target=_download_font, daemon=True).start()


def fig_to_base64(fig: plt.Figure) -> str:
    """Convert a matplotlib Figure to a base64-encoded PNG data URI."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    buf.close()
    return f"data:image/png;base64,{b64}"

_DATE_RE = re.compile(
    r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}"
    r"|^\d{1,2}[-/]\d{1,2}[-/]\d{4}"
)
_MAX_PIE_SLICES = 8
_MAX_BAR_ITEMS = 30


def _is_numeric(values: list[Any]) -> bool:
    count = 0
    for v in values:
        if v is None:
            continue
        try:
            float(v)
            count += 1
        except (ValueError, TypeError):
            return False
    return count > 0


def _is_date(values: list[Any]) -> bool:
    hits = 0
    for v in values:
        if v is None:
            continue
        if _DATE_RE.match(str(v)):
            hits += 1
        else:
            return False
    return hits > 0


def _classify_columns(
    col_values: list[tuple],
) -> tuple[list[int], list[int], list[int]]:
    """Classify column indices into categorical, numeric, and date groups."""
    cat_cols: list[int] = []
    num_cols: list[int] = []
    date_cols: list[int] = []
    for i, vals in enumerate(col_values):
        vlist = list(vals)
        if _is_numeric(vlist):
            num_cols.append(i)
        elif _is_date(vlist):
            date_cols.append(i)
        else:
            cat_cols.append(i)
    return cat_cols, num_cols, date_cols


_RANK_HINTS = re.compile(
    r"avg|average|mean|score|分|均|rank|rating|count\b|num\b|数量|max|min",
    re.I,
)
_SHARE_HINTS = re.compile(
    r"amount|sum|total|sales|revenue|额|量|费|收入|支出|占比|proportion|share",
    re.I,
)


def _looks_like_proportion(vals: list[float], columns: list[str], num_idx: int) -> bool:
    """Heuristic: return True only when pie chart is semantically appropriate.

    Pie is good for "parts of a whole" (sales by city, revenue by dept).
    Pie is bad for rankings, averages, scores, counts per individual.
    """
    import math
    col_name = columns[num_idx] if num_idx < len(columns) else ""
    if _RANK_HINTS.search(col_name):
        return False
    if _SHARE_HINTS.search(col_name):
        return True
    clean = [v for v in vals if math.isfinite(v)]
    if len(clean) < 2:
        return False
    mx = max(clean)
    mn = min(clean)
    if mx == 0:
        return False
    spread = (mx - mn) / mx
    if spread < 0.15:
        return False
    return True


def detect_chart_type(
    columns: list[str], rows: list[tuple],
) -> str | None:
    if len(columns) < 2 or len(rows) < 2:
        return None

    ncols = len(columns)
    padded = [tuple(r) + (None,) * (ncols - len(r)) if len(r) < ncols else tuple(r) for r in rows]
    col_values = list(zip(*padded)) if padded else [[] for _ in columns]
    cat_cols, num_cols, date_cols = _classify_columns(col_values)

    if not num_cols:
        return None

    if date_cols and num_cols:
        return "line"

    if cat_cols and num_cols:
        n_rows = len(rows)
        if n_rows <= _MAX_PIE_SLICES and len(num_cols) == 1:
            vals = [v for v in col_values[num_cols[0]] if v is not None]
            try:
                fvals = [float(v) for v in vals]
                all_positive = all(v >= 0 for v in fvals)
            except (ValueError, TypeError):
                all_positive = False
                fvals = []
            if all_positive and fvals and _looks_like_proportion(fvals, columns, num_cols[0]):
                return "pie"
        if n_rows <= _MAX_BAR_ITEMS:
            return "bar"
        return None

    return None


def build_chart(
    columns: list[str],
    rows: list[tuple],
    chart_type: str,
) -> plt.Figure | None:
    _configure_cjk_font()
    if not rows or not columns:
        return None

    ncols = len(columns)
    padded = [tuple(r) + (None,) * (ncols - len(r)) if len(r) < ncols else tuple(r) for r in rows]
    col_values = list(zip(*padded))

    num_cols = [i for i, vals in enumerate(col_values) if _is_numeric(list(vals))]
    date_cols = [i for i, vals in enumerate(col_values) if not _is_numeric(list(vals)) and _is_date(list(vals))]
    cat_cols = [i for i in range(ncols) if i not in num_cols and i not in date_cols]

    if not num_cols:
        return None
    label_idx = (date_cols or cat_cols or [0])[0]
    labels = [str(v) for v in col_values[label_idx]]
    values_idx = num_cols[0]
    def _safe_float(v):
        if v is None:
            return 0.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0
    values = [_safe_float(v) for v in col_values[values_idx]]
    value_label = columns[values_idx]

    if not values:
        return None

    fig, ax = plt.subplots(figsize=(5, 2.8), dpi=100)
    try:
        fig.patch.set_facecolor("#fafafa")

        if chart_type == "bar":
            ax.bar(labels, values, color="#4C78A8")
            ax.set_ylabel(value_label)
            ax.set_xlabel(columns[label_idx])
            plt.xticks(rotation=45, ha="right")
        elif chart_type == "line":
            ax.plot(labels, values, marker="o", color="#4C78A8", linewidth=2)
            ax.set_ylabel(value_label)
            ax.set_xlabel(columns[label_idx])
            plt.xticks(rotation=45, ha="right")
        elif chart_type == "pie":
            if not any(v != 0 for v in values):
                plt.close(fig)
                return None
            ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
            ax.set_title(value_label)
        elif chart_type == "scatter":
            if len(num_cols) >= 2:
                x_vals = [float(v) if v is not None else 0.0 for v in col_values[num_cols[0]]]
                y_vals = [float(v) if v is not None else 0.0 for v in col_values[num_cols[1]]]
                ax.scatter(x_vals, y_vals, color="#4C78A8", alpha=0.7)
                ax.set_xlabel(columns[num_cols[0]])
                ax.set_ylabel(columns[num_cols[1]])
            else:
                ax.scatter(range(len(values)), values, color="#4C78A8", alpha=0.7)
                ax.set_xlabel(columns[label_idx])
                ax.set_ylabel(value_label)
        else:
            plt.close(fig)
            return None

        fig.tight_layout()
        return fig
    except Exception:
        plt.close(fig)
        return None
