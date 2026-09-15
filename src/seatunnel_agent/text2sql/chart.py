"""Auto-detect chart type from query results and build matplotlib figures."""

from __future__ import annotations

import re
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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


def detect_chart_type(
    columns: list[str], rows: list[tuple],
) -> str | None:
    if len(columns) < 2 or len(rows) < 2:
        return None

    cat_cols: list[int] = []
    num_cols: list[int] = []
    date_cols: list[int] = []
    col_values = list(zip(*rows)) if rows else [[] for _ in columns]

    for i, vals in enumerate(col_values):
        vlist = list(vals)
        if _is_numeric(vlist):
            num_cols.append(i)
        elif _is_date(vlist):
            date_cols.append(i)
        else:
            cat_cols.append(i)

    if not num_cols:
        return None

    if date_cols and num_cols:
        return "line"

    if cat_cols and num_cols:
        n_rows = len(rows)
        if n_rows <= _MAX_PIE_SLICES and len(num_cols) == 1:
            vals = [v for v in col_values[num_cols[0]] if v is not None]
            if all(float(v) >= 0 for v in vals):
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
    if not rows or not columns:
        return None

    col_values = list(zip(*rows))
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

    if not num_cols:
        return None
    label_idx = (date_cols or cat_cols or [0])[0]
    labels = [str(v) for v in col_values[label_idx]]
    values_idx = num_cols[0]
    values = [float(v) if v is not None else 0.0 for v in col_values[values_idx]]
    value_label = columns[values_idx]

    fig, ax = plt.subplots(figsize=(7, 4))
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
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
        ax.set_title(value_label)
    else:
        plt.close(fig)
        return None

    fig.tight_layout()
    return fig
