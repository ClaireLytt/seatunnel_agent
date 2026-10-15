"""Sensitive-column masking at the presentation edges.

The validator guarantees *which tables* may be read; this module guards
*what leaves the tool*: values of sensitive-looking result columns (phone
numbers, ID cards, emails, bank cards) are masked in previews, exports and
push cards. Detection is by result-column name (aliases included), so it
composes with any SQL the agent generates.

Masking is ON by default; ``T2S_MASKING=0`` disables it, and
``T2S_MASK_COLUMNS=a,b,c`` adds exact extra column names (generic mask).
Raw values never change inside the engine — attribution/diff/chart math
all run on unmasked data; only the rendered copies are masked.
"""

from __future__ import annotations

import os
import re

_KIND_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("phone", re.compile(r"mobile|phone|telephone|(?:^|_)tel(?:_|$)|手机|电话",
                         re.IGNORECASE)),
    ("id", re.compile(r"id_?card|idcard|identity|passport|身份证|证件号",
                      re.IGNORECASE)),
    ("email", re.compile(r"e?mail|邮箱", re.IGNORECASE)),
    ("bank", re.compile(r"bank_?(?:card|acct|account)|card_?no|银行卡",
                        re.IGNORECASE)),
]


def masking_enabled() -> bool:
    return os.getenv("T2S_MASKING", "").strip() != "0"


def _extra_columns() -> set[str]:
    raw = os.getenv("T2S_MASK_COLUMNS", "").strip()
    return {c.strip().lower() for c in raw.split(",") if c.strip()}


def sensitive_kind(column_name: str) -> str | None:
    """The mask kind for a column name, or None when not sensitive."""
    name = (column_name or "").strip()
    if not name:
        return None
    if name.lower() in _extra_columns():
        return "generic"
    for kind, pattern in _KIND_PATTERNS:
        if pattern.search(name):
            return kind
    return None


def mask_value(value, kind: str) -> str:
    """Mask a single value; deterministic and shape-preserving-ish."""
    if value is None:
        return value
    s = str(value)
    if not s:
        return s
    if kind == "email" and "@" in s:
        local, _, domain = s.partition("@")
        head = local[0] if local else ""
        return f"{head}***@{domain}"
    if kind == "phone" and len(s) >= 7:
        return f"{s[:3]}****{s[-2:]}"
    if kind == "id" and len(s) >= 10:
        return f"{s[:4]}{'*' * (len(s) - 7)}{s[-3:]}"
    if kind == "bank" and len(s) >= 8:
        return f"{s[:4]}{'*' * (len(s) - 8)}{s[-4:]}"
    # generic / too-short values: keep the first char only
    if len(s) <= 2:
        return "*" * len(s)
    return s[0] + "*" * (len(s) - 2) + s[-1]


def apply_masking(
    columns: list[str], rows: list,
) -> tuple[list, list[str]]:
    """Mask sensitive columns; returns (rows, masked_column_names).

    No-op (same rows object) when masking is disabled or nothing matches.
    """
    if not masking_enabled() or not columns:
        return rows, []
    kinds: dict[int, str] = {}
    for i, col in enumerate(columns):
        kind = sensitive_kind(col)
        if kind:
            kinds[i] = kind
    if not kinds:
        return rows, []
    masked: list = []
    for row in rows:
        vals = list(row)
        for i, kind in kinds.items():
            if i < len(vals):
                vals[i] = mask_value(vals[i], kind)
        masked.append(tuple(vals))
    return masked, [columns[i] for i in sorted(kinds)]
