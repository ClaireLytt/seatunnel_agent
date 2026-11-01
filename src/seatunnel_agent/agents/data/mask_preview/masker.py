"""Deterministic value-level masking preview over real data rows.

pii_scan plans SQL masking from DDL and lineage; this agent works on the
*rows themselves*: paste a CSV/JSONL sample (sample_profile's parser
reused), sensitive columns are detected by name (pii_scan's rule
catalog reused) and by value shape (CN phone / ID card / email / bank
card), each gets a format-preserving mask — ``138****1234``,
``110101********1234``, ``a***@host``, ``**** **** **** 1234`` — and
the preview shows the rows before and after, ready to hand to test or
demo environments.  Nothing leaves the process.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ColumnMask", "MaskPreview", "detect_category", "mask_value",
           "preview_mask"]

# value-shape detectors: category -> regex over the raw cell
_VALUE_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("phone", re.compile(r"^1[3-9]\d{9}$")),
    ("id_card", re.compile(r"^(\d{15}|\d{17}[\dXx])$")),
    ("email", re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")),
    ("bank_card", re.compile(r"^\d{16,19}$")),
)
_VALUE_SHARE = 0.6        # share of non-null cells that must match

SEVERITY = {"phone": "high", "id_card": "high", "bank_card": "high",
            "passport": "high", "email": "medium", "person_name": "medium",
            "address": "medium", "salary": "medium", "birthday": "medium",
            "license_plate": "medium", "ip_address": "low"}


def mask_value(category: str, value: str | None) -> str | None:
    """Format-preserving mask for one cell; None passes through."""
    if value is None or value == "":
        return value
    v = str(value)
    if category == "phone":
        return v[:3] + "****" + v[-4:] if len(v) >= 8 else "*" * len(v)
    if category == "id_card":
        return v[:6] + "*" * 8 + v[-4:] if len(v) >= 12 else "*" * len(v)
    if category == "email":
        head, _, domain = v.partition("@")
        return (head[:1] + "***@" + domain) if domain else v[:1] + "***"
    if category == "bank_card":
        return "**** **** **** " + v[-4:] if len(v) >= 8 else "*" * len(v)
    if category == "person_name":
        return v[:1] + "*" * max(1, len(v) - 1)
    if category == "address":
        return v[:6] + "****" if len(v) > 6 else v[:1] + "****"
    if category in ("salary",):
        return "***"
    if category == "ip_address":
        return re.sub(r"(\d+)\.(\d+)$", "*.*", v)
    # passport / birthday / license_plate / anything else: edge-preserving
    if len(v) <= 2:
        return "*" * len(v)
    return v[:1] + "*" * (len(v) - 2) + v[-1:]


@dataclass
class ColumnMask:
    name: str
    category: str        # pii_scan category
    severity: str        # high | medium | low
    detected_by: str     # name | value | name+value
    sample_before: str = ""
    sample_after: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "category": self.category,
                "severity": self.severity, "detected_by": self.detected_by,
                "sample_before": self.sample_before,
                "sample_after": self.sample_after}


@dataclass
class MaskPreview:
    headers: list[str]
    rows_total: int
    columns: list[ColumnMask] = field(default_factory=list)
    masked_rows: list[dict[str, str | None]] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.columns

    def to_dict(self) -> dict[str, Any]:
        return {"headers": list(self.headers),
                "rows_total": self.rows_total,
                "sensitive_columns": len(self.columns),
                "clean": self.clean,
                "columns": [c.to_dict() for c in self.columns],
                "masked_rows": [dict(r) for r in self.masked_rows]}


def _detect_by_name(header: str) -> str | None:
    from seatunnel_agent.agents.data.pii_scan.rules import DEFAULT_RULES

    low = header.lower()
    for rule in DEFAULT_RULES:
        strong, weak = rule.compiled()
        if any(p.search(low) for p in strong + weak):
            return rule.category
    return None


def _detect_by_value(values: list[str]) -> str | None:
    if not values:
        return None
    for category, pattern in _VALUE_PATTERNS:
        hits = sum(1 for v in values if pattern.match(v))
        if hits / len(values) >= _VALUE_SHARE:
            return category
    return None


def detect_category(name: str, values: list[str]) -> str | None:
    """Public seam: sensitive category of a column, by name (pii_scan's
    catalog) first and value shape second — mock_data synthesizes fakes
    through this instead of reaching into the private detectors."""
    return _detect_by_name(name) or _detect_by_value(values)


def preview_mask(headers: list[str], rows: list[dict[str, str | None]],
                 preview_rows: int = 20) -> MaskPreview:
    """Parsed rows → sensitive-column masks + before/after preview."""
    if not headers:
        raise ValueError("no columns to preview")
    if preview_rows < 1:
        raise ValueError("preview_rows must be positive")

    preview = MaskPreview(headers=list(headers), rows_total=len(rows))
    categories: dict[str, str] = {}
    for h in headers:
        values = [str(r[h]) for r in rows
                  if r.get(h) not in (None, "")][:200]
        by_name = _detect_by_name(h)
        by_value = _detect_by_value(values)
        category = by_name or by_value
        if category is None:
            continue
        detected = ("name+value" if by_name and by_value == by_name
                    else "name" if by_name else "value")
        before = values[0] if values else ""
        preview.columns.append(ColumnMask(
            name=h, category=category,
            severity=SEVERITY.get(category, "medium"),
            detected_by=detected, sample_before=before,
            sample_after=str(mask_value(category, before) or "")))
        categories[h] = category

    for row in rows[:preview_rows]:
        preview.masked_rows.append({
            h: (mask_value(categories[h], row.get(h))
                if h in categories else row.get(h))
            for h in headers})
    order = {"high": 0, "medium": 1, "low": 2}
    preview.columns.sort(key=lambda c: (order[c.severity], c.name))
    return preview
