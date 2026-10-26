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

#: official holiday spans by year and name — the single source both for
#: the flat HOLIDAYS set and for named-range lookups ("春节期间的 GMV")
HOLIDAY_RANGES: dict[int, dict[str, tuple[date, date]]] = {
    # ---- 2024 (国办发明电〔2023〕7号) ----
    2024: {
        "元旦": (date(2024, 1, 1), date(2024, 1, 1)),
        "春节": (date(2024, 2, 10), date(2024, 2, 17)),
        "清明": (date(2024, 4, 4), date(2024, 4, 6)),
        "劳动节": (date(2024, 5, 1), date(2024, 5, 5)),
        "端午": (date(2024, 6, 10), date(2024, 6, 10)),
        "中秋": (date(2024, 9, 15), date(2024, 9, 17)),
        "国庆": (date(2024, 10, 1), date(2024, 10, 7)),
    },
    # ---- 2025 (国办发明电〔2024〕12号) ----
    2025: {
        "元旦": (date(2025, 1, 1), date(2025, 1, 1)),
        "春节": (date(2025, 1, 28), date(2025, 2, 4)),
        "清明": (date(2025, 4, 4), date(2025, 4, 6)),
        "劳动节": (date(2025, 5, 1), date(2025, 5, 5)),
        "端午": (date(2025, 5, 31), date(2025, 6, 2)),
        # 国庆与中秋连休一个区间,两个名字指向同一官方区间
        "中秋": (date(2025, 10, 1), date(2025, 10, 8)),
        "国庆": (date(2025, 10, 1), date(2025, 10, 8)),
    },
    # ---- 2026 (国办发明电〔2025〕7号) ----
    2026: {
        "元旦": (date(2026, 1, 1), date(2026, 1, 3)),
        "春节": (date(2026, 2, 15), date(2026, 2, 23)),
        "清明": (date(2026, 4, 4), date(2026, 4, 6)),
        "劳动节": (date(2026, 5, 1), date(2026, 5, 5)),
        "端午": (date(2026, 6, 19), date(2026, 6, 21)),
        "中秋": (date(2026, 9, 25), date(2026, 9, 27)),
        "国庆": (date(2026, 10, 1), date(2026, 10, 7)),
    },
}

#: statutory holiday days (放假日, includes weekend days inside the span)
HOLIDAYS: frozenset[date] = frozenset(
    d
    for ranges in HOLIDAY_RANGES.values()
    for start, end in set(ranges.values())
    for d in _span(start, end)
)

_HOLIDAY_ALIASES = {
    "五一": "劳动节", "劳动": "劳动节",
    "十一": "国庆", "国庆节": "国庆",
    "新年": "元旦", "元旦节": "元旦",
    "过年": "春节", "春节假期": "春节",
    "清明节": "清明", "端午节": "端午", "中秋节": "中秋",
}


def named_holiday_range(text: str, today: date) -> tuple[date, date] | None:
    """Official span for a holiday name like ``春节`` / ``2025国庆`` / ``五一期间``.

    Without an explicit year, the most recent occurrence whose start is on
    or before *today* wins (asking about 春节 in October means this year's,
    not next year's). Unknown names or uncovered years return None — the
    caller falls back to normal date parsing, never guesses.
    """
    import re

    t = text.strip()
    m = re.fullmatch(r"(?:(\d{4})\s*年?)?\s*(\S+?)\s*(?:期间|假期)?", t)
    if not m:
        return None
    year_raw, name = m.group(1), m.group(2)
    name = _HOLIDAY_ALIASES.get(name, name)
    if year_raw:
        ranges = HOLIDAY_RANGES.get(int(year_raw), {})
        return ranges.get(name)
    candidates = [
        rng
        for year in sorted(HOLIDAY_RANGES)
        for n, rng in HOLIDAY_RANGES[year].items()
        if n == name and rng[0] <= today
    ]
    return candidates[-1] if candidates else None

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
