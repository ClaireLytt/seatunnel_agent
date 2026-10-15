# -*- coding: utf-8 -*-
"""Zero-dependency cron parsing + built-in template params for subscriptions.

Moved verbatim out of subscriptions.py, which re-exports the public names.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .partition import pt_value


# ----------------------------------------------------------------------
# Cron (standard 5 fields, zero-dep)
# ----------------------------------------------------------------------

_FIELD_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
_FIELD_NAMES = ("minute", "hour", "day-of-month", "month", "day-of-week")


def _parse_field(expr: str, lo: int, hi: int, name: str) -> frozenset[int]:
    values: set[int] = set()
    for part in expr.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            try:
                step = int(step_s)
            except ValueError:
                raise ValueError(f"cron {name}: 无效步长 '{step_s}'")
            if step < 1:
                raise ValueError(f"cron {name}: 步长必须 >= 1")
        if part in ("*", ""):
            start, end = lo, hi
        elif "-" in part:
            a, b = part.split("-", 1)
            try:
                start, end = int(a), int(b)
            except ValueError:
                raise ValueError(f"cron {name}: 无效范围 '{part}'")
        else:
            try:
                start = end = int(part)
            except ValueError:
                raise ValueError(f"cron {name}: 无效值 '{part}'")
        if not (lo <= start <= hi and lo <= end <= hi and start <= end):
            raise ValueError(f"cron {name}: 取值需在 {lo}-{hi} 内")
        values.update(range(start, end + 1, step))
    return frozenset(values)


@dataclass(frozen=True)
class CronSpec:
    minute: frozenset[int]
    hour: frozenset[int]
    dom: frozenset[int]
    month: frozenset[int]
    dow: frozenset[int]  # 0 = Monday (Python convention), 6 = Sunday

    def matches(self, dt: datetime) -> bool:
        return (
            dt.minute in self.minute
            and dt.hour in self.hour
            and dt.day in self.dom
            and dt.month in self.month
            and dt.weekday() in self.dow
        )


def parse_cron(expr: str) -> CronSpec:
    """Parse ``M H DoM Mon DoW``. Day-of-week: 0=Monday .. 6=Sunday
    (7 is accepted as Sunday for cron habit)."""
    fields = (expr or "").split()
    if len(fields) != 5:
        raise ValueError("cron 表达式必须是 5 个字段: 分 时 日 月 周")
    parsed = []
    for raw, (lo, hi), name in zip(fields, _FIELD_RANGES, _FIELD_NAMES):
        if name == "day-of-week":
            raw = raw.replace("7", "6") if raw.strip() == "7" else raw
        parsed.append(_parse_field(raw, lo, hi, name))
    return CronSpec(*parsed)


# ----------------------------------------------------------------------
# Built-in date macros for favorite params
# ----------------------------------------------------------------------


def builtin_params(today: date | None = None) -> dict[str, str]:
    """Date macros usable as ``${name}`` in favorite SQL / extra filters."""
    today = today or date.today()
    yesterday = today - timedelta(days=1)
    month_start = today.replace(day=1)
    return {
        "today": today.isoformat(),
        "yesterday": yesterday.isoformat(),
        "today_pt": pt_value(today),
        "yesterday_pt": pt_value(yesterday),
        "month_start": month_start.isoformat(),
        "month_start_pt": pt_value(month_start),
    }


