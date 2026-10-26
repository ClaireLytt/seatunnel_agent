"""Chinese statutory holiday calendar (法定节假日) — static, offline.

Dates are transcribed verbatim from the State Council General Office
notices (国务院办公厅关于XX年部分节假日安排的通知):

- 2024: 国办发明电〔2023〕7号
- 2025: 国办发明电〔2024〕12号
- 2026: 国办发明电〔2025〕7号

2027 has not been announced as of 2026-10 (usually published each
November); dates outside :data:`CALENDAR_YEARS` are simply "not covered"
and callers must degrade gracefully instead of guessing.
"""

from __future__ import annotations

from datetime import date, timedelta


def _span(start: date, end: date) -> list[date]:
    out = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=1)
    return out


#: years whose official schedule is encoded below
CALENDAR_YEARS = frozenset({2024, 2025, 2026})

#: statutory holiday days (放假日, includes weekend days inside the span)
HOLIDAYS: frozenset[date] = frozenset(
    # ---- 2024 (国办发明电〔2023〕7号) ----
    [date(2024, 1, 1)]                                   # 元旦
    + _span(date(2024, 2, 10), date(2024, 2, 17))        # 春节
    + _span(date(2024, 4, 4), date(2024, 4, 6))          # 清明
    + _span(date(2024, 5, 1), date(2024, 5, 5))          # 劳动节
    + [date(2024, 6, 10)]                                # 端午
    + _span(date(2024, 9, 15), date(2024, 9, 17))        # 中秋
    + _span(date(2024, 10, 1), date(2024, 10, 7))        # 国庆
    # ---- 2025 (国办发明电〔2024〕12号) ----
    + [date(2025, 1, 1)]                                 # 元旦
    + _span(date(2025, 1, 28), date(2025, 2, 4))         # 春节
    + _span(date(2025, 4, 4), date(2025, 4, 6))          # 清明
    + _span(date(2025, 5, 1), date(2025, 5, 5))          # 劳动节
    + _span(date(2025, 5, 31), date(2025, 6, 2))         # 端午
    + _span(date(2025, 10, 1), date(2025, 10, 8))        # 国庆+中秋
    # ---- 2026 (国办发明电〔2025〕7号) ----
    + _span(date(2026, 1, 1), date(2026, 1, 3))          # 元旦
    + _span(date(2026, 2, 15), date(2026, 2, 23))        # 春节
    + _span(date(2026, 4, 4), date(2026, 4, 6))          # 清明
    + _span(date(2026, 5, 1), date(2026, 5, 5))          # 劳动节
    + _span(date(2026, 6, 19), date(2026, 6, 21))        # 端午
    + _span(date(2026, 9, 25), date(2026, 9, 27))        # 中秋
    + _span(date(2026, 10, 1), date(2026, 10, 7))        # 国庆
)

#: makeup workdays (调休上班日 — weekends that behave like workdays)
MAKEUP_WORKDAYS: frozenset[date] = frozenset([
    # 2024
    date(2024, 2, 4), date(2024, 2, 18),                 # 春节
    date(2024, 4, 7),                                    # 清明
    date(2024, 4, 28), date(2024, 5, 11),                # 劳动节
    date(2024, 9, 14),                                   # 中秋
    date(2024, 9, 29), date(2024, 10, 12),               # 国庆
    # 2025
    date(2025, 1, 26), date(2025, 2, 8),                 # 春节
    date(2025, 4, 27),                                   # 劳动节
    date(2025, 9, 28), date(2025, 10, 11),               # 国庆+中秋
    # 2026
    date(2026, 1, 4),                                    # 元旦
    date(2026, 2, 14), date(2026, 2, 28),                # 春节
    date(2026, 5, 9),                                    # 劳动节
    date(2026, 9, 20), date(2026, 10, 10),               # 国庆
])


def covers(d: date) -> bool:
    """Whether the calendar has official data for ``d``'s year."""
    return d.year in CALENDAR_YEARS


def is_holiday(d: date) -> bool:
    """Statutory holiday day. False for uncovered years (degrade, not guess)."""
    return d in HOLIDAYS


def is_makeup_workday(d: date) -> bool:
    """Makeup workday (调休上班的周末). False for uncovered years."""
    return d in MAKEUP_WORKDAYS
