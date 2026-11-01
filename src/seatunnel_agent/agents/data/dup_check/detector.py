"""Deterministic duplicate detection over raw data rows.

Reuses the sample_profile parser (CSV with a header row, or JSONL) and
checks three layers: full-row duplicates, primary-key duplicates (same
key, otherwise different rows) and business-event duplicates (declared
key combination).  Every group reports its size, first/last row numbers
and — for key duplicates — the columns that differ, which is what
locates the source of the duplication (retry vs upstream fan-out vs a
missing dedup window).  No database connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from seatunnel_agent.agents.data.sample_profile import parse_rows

__all__ = ["DupGroup", "DupResult", "detect_dups"]

_MAX_GROUPS = 50       # reported per layer; totals stay exact


@dataclass
class DupGroup:
    layer: str                      # row / pk / biz
    key: str                        # rendered key value(s)
    count: int
    first_row: int
    last_row: int
    diff_columns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"layer": self.layer, "key": self.key, "count": self.count,
                "first_row": self.first_row, "last_row": self.last_row,
                "diff_columns": self.diff_columns}


@dataclass
class DupResult:
    total_rows: int
    pk_columns: list[str]
    biz_columns: list[str]
    row_dup_rows: int
    pk_dup_rows: int
    biz_dup_rows: int
    groups: list[DupGroup]

    def to_dict(self) -> dict:
        return {"total_rows": self.total_rows,
                "pk_columns": self.pk_columns,
                "biz_columns": self.biz_columns,
                "row_dup_rows": self.row_dup_rows,
                "pk_dup_rows": self.pk_dup_rows,
                "biz_dup_rows": self.biz_dup_rows,
                "groups": [g.to_dict() for g in self.groups]}


def _split_keys(spec: str | None, headers: list[str],
                what: str) -> list[str]:
    cols = [c.strip() for c in (spec or "").split(",") if c.strip()]
    missing = [c for c in cols if c not in headers]
    if missing:
        raise ValueError(f"{what} column(s) not in data: "
                         f"{', '.join(missing)} / 列不存在")
    return cols


def _group_by(rows: list[dict[str, str | None]],
              cols: list[str]) -> dict[tuple, list[int]]:
    """Key tuple -> 1-indexed row numbers; rows with a null key skipped."""
    groups: dict[tuple, list[int]] = {}
    for i, row in enumerate(rows, start=1):
        key = tuple(row.get(c) for c in cols)
        if any(v is None for v in key):
            continue
        groups.setdefault(key, []).append(i)
    return groups


def _diff_columns(rows: list[dict[str, str | None]], headers: list[str],
                  members: list[int], key_cols: list[str]) -> list[str]:
    diff = []
    for col in headers:
        if col in key_cols:
            continue
        values = {rows[i - 1].get(col) for i in members}
        if len(values) > 1:
            diff.append(col)
    return diff


def detect_dups(text: str, pk: str | None = None,
                biz_key: str | None = None) -> DupResult:
    headers, rows = parse_rows(text)
    pk_cols = _split_keys(pk, headers, "primary-key")
    biz_cols = _split_keys(biz_key, headers, "business-key")

    groups: list[DupGroup] = []
    counts = {"row": 0, "pk": 0, "biz": 0}

    # layer 1: full-row duplicates (always on)
    layer_specs: list[tuple[str, list[str]]] = [("row", headers)]
    if pk_cols:
        layer_specs.append(("pk", pk_cols))
    if biz_cols and biz_cols != pk_cols:
        layer_specs.append(("biz", biz_cols))

    row_dup_members: set[int] = set()
    for layer, cols in layer_specs:
        for key, members in sorted(_group_by(rows, cols).items(),
                                   key=lambda kv: (-len(kv[1]), kv[1][0])):
            if len(members) < 2:
                continue
            if layer == "row":
                row_dup_members.update(members)
            elif set(members) <= row_dup_members:
                continue  # already reported as identical rows
            counts[layer] += len(members) - 1
            if sum(1 for g in groups if g.layer == layer) >= _MAX_GROUPS:
                continue
            diff = ([] if layer == "row"
                    else _diff_columns(rows, headers, members, cols))
            groups.append(DupGroup(
                layer=layer,
                key=", ".join("∅" if v is None else v for v in key),
                count=len(members), first_row=members[0],
                last_row=members[-1], diff_columns=diff))

    order = {"row": 0, "pk": 1, "biz": 2}
    groups.sort(key=lambda g: (order[g.layer], -g.count, g.first_row))
    return DupResult(
        total_rows=len(rows), pk_columns=pk_cols, biz_columns=biz_cols,
        row_dup_rows=counts["row"], pk_dup_rows=counts["pk"],
        biz_dup_rows=counts["biz"], groups=groups)
