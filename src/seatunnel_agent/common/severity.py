"""Shared severity marks for the high/medium/low report family.

One map instead of a per-report copy (the review found five identical
dicts under two names). Geometric glyphs, not emoji — the UI 设计规范
bans emoji, and the filled/half/open circle carries the intensity scale
in any font: ● high, ◐ medium, ○ low.
"""

from __future__ import annotations

SEVERITY_MARK = {"high": "●", "medium": "◐", "low": "○"}
