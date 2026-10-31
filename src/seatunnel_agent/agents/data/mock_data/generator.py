"""Deterministic mock-data generation from a real sample's shape.

Test environments need rows that *look* like production without *being*
production.  Paste a sample (sample_profile's parser and column
profiles reused): every column keeps its shape — integers and decimals
stay in the observed range, dates stay in the observed window and
format, low-cardinality columns draw from the observed value
distribution, null rates carry over — while sensitive columns
(mask_preview's detectors reused) are **synthesized, never sampled**:
fake phones, fake ID numbers, fake emails and fake names that match the
format but never equal a real value.  Seeded, so the same input and
seed always generate the same rows.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

__all__ = ["ColumnPlan", "MockResult", "generate_mock"]

_ENUM_MAX_DISTINCT = 12       # distinct values at or below this -> enum
_ENUM_UNIQUE_PCT = 30.0       # or unique share below this -> enum
_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_INT_RE = re.compile(r"^-?\d+$")
_SURNAMES = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许"
_GIVEN = "伟芳娜敏静磊洋勇艳杰涛明超秀兰霞平刚桂英"


@dataclass
class ColumnPlan:
    name: str
    strategy: str        # sequence|int_range|float_range|date_range|
    #                      enum|fake_<category>|text|null
    detail: str = ""     # human-readable parameters

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "strategy": self.strategy,
                "detail": self.detail}


@dataclass
class MockResult:
    headers: list[str]
    rows_generated: int
    seed: int
    sample_rows: int = 0
    plans: list[ColumnPlan] = field(default_factory=list)
    rows: list[dict[str, str | None]] = field(default_factory=list)

    def to_csv(self) -> str:
        import csv
        import io

        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(self.headers)
        for r in self.rows:
            w.writerow(["" if r[h] is None else r[h] for h in self.headers])
        return buf.getvalue()

    def to_dict(self) -> dict[str, Any]:
        return {"headers": list(self.headers),
                "rows_generated": self.rows_generated,
                "seed": self.seed,
                "sample_rows": self.sample_rows,
                "plans": [p.to_dict() for p in self.plans],
                "rows": [dict(r) for r in self.rows],
                "csv": self.to_csv()}


def _fake(category: str, rng: random.Random) -> str:
    if category == "phone":
        return "13" + str(rng.randint(0, 9)) + f"{rng.randint(0, 99999999):08d}"
    if category == "id_card":
        return (f"{rng.randint(110000, 659000):06d}"
                f"{rng.randint(1950, 2005):04d}"
                f"{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}"
                f"{rng.randint(0, 999):03d}{rng.choice('0123456789X')}")
    if category == "email":
        user = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                       for _ in range(6))
        return f"{user}@example.com"
    if category == "bank_card":
        return "62" + "".join(str(rng.randint(0, 9)) for _ in range(14))
    if category == "person_name":
        return rng.choice(_SURNAMES) + "".join(
            rng.choice(_GIVEN) for _ in range(rng.randint(1, 2)))
    if category == "address":
        return f"测试市示例区模拟路{rng.randint(1, 999)}号"
    if category == "ip_address":
        return ".".join(str(rng.randint(1, 254)) for _ in range(4))
    # passport / salary / birthday / license_plate and anything else
    return "MOCK" + f"{rng.randint(0, 99999):05d}"


def _decimals(values: list[str]) -> int:
    places = [len(v.split(".", 1)[1]) for v in values if "." in v]
    return max(places) if places else 2


def _plan_column(name: str, values: list[str], profile) -> ColumnPlan:
    from seatunnel_agent.agents.data.mask_preview import detect_category

    category = detect_category(name, values[:200])
    if category:
        return ColumnPlan(name, f"fake_{category}", category)
    if not values:
        return ColumnPlan(name, "null", "all null in sample")
    distinct = len(set(values))
    if profile.kind == "integer" and distinct == len(values):
        return ColumnPlan(name, "sequence",
                          f"start {int(max(int(v) for v in values)) + 1}")
    if (distinct <= _ENUM_MAX_DISTINCT
            or profile.unique_pct < _ENUM_UNIQUE_PCT):
        return ColumnPlan(name, "enum", f"{distinct} values")
    if profile.kind == "integer":
        return ColumnPlan(name, "int_range",
                          f"[{int(profile.vmin)}, {int(profile.vmax)}]")
    if profile.kind == "decimal":
        return ColumnPlan(name, "float_range",
                          f"[{profile.vmin:g}, {profile.vmax:g}]")
    if profile.kind in ("date", "datetime", "date_slash"):
        ds = sorted(v[:10] for v in values if _DATE_RE.match(v))
        if ds:
            return ColumnPlan(name, "date_range", f"{ds[0]} .. {ds[-1]}")
    return ColumnPlan(name, "text",
                      f"len {min(len(v) for v in values)}-"
                      f"{max(len(v) for v in values)}")


def _emit(plan: ColumnPlan, values: list[str], rng: random.Random,
          seq_state: dict[str, int]) -> str:
    if plan.strategy.startswith("fake_"):
        return _fake(plan.strategy[5:], rng)
    if plan.strategy == "sequence":
        seq_state[plan.name] = seq_state.get(
            plan.name, int(plan.detail.split()[-1])) + 1
        return str(seq_state[plan.name] - 1)
    if plan.strategy == "enum":
        return rng.choice(values)
    if plan.strategy == "int_range":
        lo, hi = min(map(int, values)), max(map(int, values))
        return str(rng.randint(lo, hi))
    if plan.strategy == "float_range":
        lo, hi = min(map(float, values)), max(map(float, values))
        return f"{rng.uniform(lo, hi):.{_decimals(values)}f}"
    if plan.strategy == "date_range":
        ds = sorted(v[:10] for v in values if _DATE_RE.match(v))
        d0 = date.fromisoformat(ds[0])
        span = (date.fromisoformat(ds[-1]) - d0).days
        return (d0 + timedelta(days=rng.randint(0, max(span, 0)))).isoformat()
    # text: random lowercase of a sampled length
    length = len(rng.choice(values)) if values else 6
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                   for _ in range(max(length, 1)))


def generate_mock(headers: list[str], rows: list[dict[str, str | None]],
                  count: int = 50, seed: int = 42) -> MockResult:
    """Sample rows → *count* deterministic mock rows of the same shape."""
    from seatunnel_agent.agents.data.sample_profile import profile_rows

    if not headers:
        raise ValueError("no columns in the sample")
    if not rows:
        raise ValueError("the sample has no rows")
    if not 1 <= count <= 10000:
        raise ValueError("count must be within [1, 10000]")

    profiles = {p.name: p for p in profile_rows(headers, rows).columns}
    col_values = {h: [str(r[h]) for r in rows if r.get(h) not in (None, "")]
                  for h in headers}
    null_rate = {h: 1 - len(col_values[h]) / len(rows) for h in headers}
    plans = [_plan_column(h, col_values[h], profiles[h]) for h in headers]

    rng = random.Random(seed)
    seq_state: dict[str, int] = {}
    out_rows: list[dict[str, str | None]] = []
    for _ in range(count):
        row: dict[str, str | None] = {}
        for plan in plans:
            if plan.strategy == "null" or rng.random() < null_rate[plan.name]:
                row[plan.name] = None
                continue
            row[plan.name] = _emit(plan, col_values[plan.name], rng,
                                   seq_state)
        out_rows.append(row)
    return MockResult(headers=list(headers), rows_generated=count,
                      seed=seed, sample_rows=len(rows), plans=plans,
                      rows=out_rows)
