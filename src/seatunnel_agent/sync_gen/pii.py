# -*- coding: utf-8 -*-
"""PII column detection + masking expression builder for sync configs.

Rule matching is shared with the pii_scan module (one source of truth:
``pii_scan.rules.match_column``). Only high-confidence hits (strong name
pattern or Chinese comment keyword) are auto-masked; weak hits are
reported in the manifest for human review but left untouched — a bare
``name`` column is too often not a person's name to mangle blindly.

Both strategies emit functions in pii_scan's MASKING_FUNCS, so a
downstream ``seatunnel-agent pii`` run sees the propagation as masked.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..pii_scan.rules import DEFAULT_RULES, PiiRule, load_extra_rules, match_column
from .model import TableSpec

STRATEGIES = ("md5", "mask")


@dataclass
class PiiHit:
    column: str
    category: str
    severity: str
    confidence: str      # high | low
    evidence: str
    masked: bool         # 是否自动脱敏（low 置信只报告不动手）


def load_rules(extra_path: str | None = None) -> list[PiiRule]:
    rules = list(DEFAULT_RULES)
    if extra_path:
        rules.extend(load_extra_rules(extra_path))
    return rules


def scan_table(spec: TableSpec, rules: list[PiiRule]) -> list[PiiHit]:
    hits: list[PiiHit] = []
    for col in spec.columns:
        m = match_column(col.name, col.comment, rules)
        if m is None:
            continue
        rule, confidence, _matched_by, evidence = m
        hits.append(PiiHit(
            column=col.name, category=rule.category, severity=rule.severity,
            confidence=confidence, evidence=evidence,
            masked=confidence == "high"))
    return hits


def mask_expr(column: str, strategy: str) -> str:
    """Masking SQL expression for one column (SeaTunnel SQL transform)."""
    if strategy == "mask":
        return f"concat(substring({column}, 1, 3), '****') AS {column}"
    return f"md5({column}) AS {column}"
