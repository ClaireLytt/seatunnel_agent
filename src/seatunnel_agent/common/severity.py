"""Shared severity marks for the high/medium/low report family.

One map instead of a per-report copy (the review found five identical
dicts under two names). Geometric glyphs, not emoji — the UI 设计规范
bans emoji, and the filled/half/open circle carries the intensity scale
in any font: ● high, ◐ medium, ○ low.
"""

from __future__ import annotations

SEVERITY_MARK = {"high": "●", "medium": "◐", "low": "○"}

# the error/warn/info and breaking/risk/info families share the same scale
LEVEL_MARK = {"error": "●", "warn": "◐", "info": "○"}
DRIFT_MARK = {"breaking": "●", "risk": "◐", "info": "○"}


SEVERITY_ORDER = ("high", "medium", "low")


def severity_counts(items, keys=SEVERITY_ORDER,
                    attr: str = "severity") -> dict[str, int]:
    """Tally items by severity plus a total — one loop instead of the
    per-report copy this review found in eight checkers."""
    out = dict.fromkeys(keys, 0)
    for item in items:
        out[getattr(item, attr)] += 1
    out["total"] = len(items)
    return out
