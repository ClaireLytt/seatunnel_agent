"""Deterministic asset-value grading over an inventory listing.

The inventory comes in as CSV (``table,size_gb,access_cnt_30d,
last_access,downstream_cnt`` header, extra columns ignored) or a JSON
list with the same fields.  Every asset gets a transparent value score —
access frequency (log-scaled), downstream dependency count, and access
recency — and a tier (core / common / edge / idle), plus a value x cost
quadrant against the inventory's median size, so "big but idle" and
"small but core" pop out.  storage_cost reuses this parser.  No
database connection.
"""

from __future__ import annotations

import csv
import io
import json
import math
from dataclasses import dataclass, field
from datetime import date

__all__ = ["AssetRow", "AssetValue", "ValueResult", "parse_inventory",
           "value_assets"]

_TIERS = (("core", 60.0), ("common", 35.0), ("edge", 15.0))


@dataclass
class AssetRow:
    table: str
    size_gb: float = 0.0
    access_cnt_30d: int = 0
    last_access: str = ""
    downstream_cnt: int = 0
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"table": self.table, "size_gb": self.size_gb,
                "access_cnt_30d": self.access_cnt_30d,
                "last_access": self.last_access,
                "downstream_cnt": self.downstream_cnt, **self.extra}


@dataclass
class AssetValue:
    table: str
    score: float
    tier: str
    quadrant: str
    size_gb: float
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"table": self.table, "score": round(self.score, 1),
                "tier": self.tier, "quadrant": self.quadrant,
                "size_gb": self.size_gb, "evidence": self.evidence}


@dataclass
class ValueResult:
    today: str
    median_size_gb: float
    tiers: dict[str, int]
    assets: list[AssetValue]

    def to_dict(self) -> dict:
        return {"today": self.today,
                "median_size_gb": self.median_size_gb,
                "tiers": self.tiers,
                "assets": [a.to_dict() for a in self.assets]}


_KNOWN = {"table", "size_gb", "access_cnt_30d", "last_access",
          "downstream_cnt"}


def parse_inventory(text: str) -> list[AssetRow]:
    body = (text or "").strip()
    if not body:
        raise ValueError("empty inventory / 资产清单为空")
    if body.startswith("["):
        items = json.loads(body)
    else:
        items = [dict(r) for r in csv.DictReader(io.StringIO(body))]
    rows: list[AssetRow] = []
    for i, it in enumerate(items, start=1):
        if not isinstance(it, dict) or not (it.get("table") or "").strip():
            raise ValueError(f"item {i}: needs 'table' / 第 {i} 项缺 table")
        try:
            rows.append(AssetRow(
                table=str(it["table"]).strip(),
                size_gb=float(it.get("size_gb") or 0),
                access_cnt_30d=int(float(it.get("access_cnt_30d") or 0)),
                last_access=str(it.get("last_access") or "").strip(),
                downstream_cnt=int(float(it.get("downstream_cnt") or 0)),
                extra={k: v for k, v in it.items() if k not in _KNOWN}))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"item {i} ({it.get('table')}): {exc}") from exc
    if not rows:
        raise ValueError("empty inventory / 资产清单为空")
    return rows


def _days_since(day: str, today: date) -> int | None:
    try:
        return (today - date.fromisoformat(day)).days
    except ValueError:
        return None


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def value_assets(rows: list[AssetRow],
                 today: date | None = None) -> ValueResult:
    today = today or date.today()
    median_size = _median([r.size_gb for r in rows]) if rows else 0.0
    assets: list[AssetValue] = []
    for r in rows:
        access_pts = min(50.0, 8.0 * math.log2(1 + r.access_cnt_30d))
        deps_pts = min(30.0, 6.0 * r.downstream_cnt)
        days = _days_since(r.last_access, today)
        if days is None:
            recency_pts = 0.0
        elif days <= 7:
            recency_pts = 20.0
        elif days <= 30:
            recency_pts = 10.0
        elif days <= 90:
            recency_pts = 5.0
        else:
            recency_pts = 0.0
        score = access_pts + deps_pts + recency_pts
        tier = "idle"
        for name, floor in _TIERS:
            if score >= floor:
                tier = name
                break
        high_cost = r.size_gb > median_size
        high_value = score >= 35.0
        quadrant = (("core-heavy" if high_cost else "core-light")
                    if high_value else
                    ("idle-heavy" if high_cost else "idle-light"))
        assets.append(AssetValue(
            table=r.table, score=score, tier=tier, quadrant=quadrant,
            size_gb=r.size_gb, evidence={
                "access_pts": round(access_pts, 1),
                "deps_pts": round(deps_pts, 1),
                "recency_pts": recency_pts,
                "access_cnt_30d": r.access_cnt_30d,
                "downstream_cnt": r.downstream_cnt,
                "days_since_access": days}))
    assets.sort(key=lambda a: (-a.score, a.table))
    tiers: dict[str, int] = {"core": 0, "common": 0, "edge": 0, "idle": 0}
    for a in assets:
        tiers[a.tier] += 1
    return ValueResult(today=today.isoformat(),
                       median_size_gb=median_size, tiers=tiers,
                       assets=assets)
