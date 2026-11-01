"""Deterministic consistency-repair planning over raw data rows.

Reuses the sample_profile profiler and the dup_check detector on the
pasted rows, then turns every confirmed issue into a copy-ready repair
action: a ROW_NUMBER dedup for duplicate groups, COALESCE backfill
candidates for high-null columns, TRIM/UPPER standardization for
whitespace and case drift, numeric cleanup casts for numbers stored as
text, and a CASE rewrite template for outlier formats.  SQL templates
target Hive/Spark-compatible syntax; placeholders that need a human
decision stay as <angle-bracket> markers.  No database connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from seatunnel_agent.agents.data.dup_check import detect_dups
from seatunnel_agent.agents.data.sample_profile import (
    parse_rows,
    profile_rows,
    sample_rows,
)

__all__ = ["RepairAction", "RepairPlan", "plan_repairs"]


@dataclass
class RepairAction:
    kind: str              # dedup / null_backfill / standardize / numeric_cast / format_fix
    severity: str          # high / mid / low
    column: str            # "" for table-level actions
    rationale: dict = field(default_factory=dict)
    sql: str = ""

    def to_dict(self) -> dict:
        return {"kind": self.kind, "severity": self.severity,
                "column": self.column, "rationale": self.rationale,
                "sql": self.sql}


@dataclass
class RepairPlan:
    table: str
    total_rows: int
    actions: list[RepairAction]

    def to_dict(self) -> dict:
        return {"table": self.table, "total_rows": self.total_rows,
                "actions": [a.to_dict() for a in self.actions]}


def _dedup_sql(table: str, key_cols: list[str], all_cols: list[str]) -> str:
    partition = ", ".join(key_cols) if key_cols else ", ".join(all_cols)
    order = key_cols[0] if key_cols else all_cols[0]
    return (f"-- keep one row per ({partition}); pick the survivor "
            f"deliberately via ORDER BY\n"
            f"INSERT OVERWRITE TABLE {table}\n"
            f"SELECT {', '.join(all_cols)} FROM (\n"
            f"  SELECT *, ROW_NUMBER() OVER (\n"
            f"    PARTITION BY {partition} ORDER BY {order}) AS rn\n"
            f"  FROM {table}\n"
            f") t WHERE rn = 1;")


def plan_repairs(text: str, table: str = "<table>", pk: str | None = None,
                 biz_key: str | None = None,
                 max_rows: int = 2000) -> RepairPlan:
    headers, rows = parse_rows(text)
    profile = profile_rows(headers, sample_rows(rows, max_rows),
                           total_rows=len(rows))
    dups = detect_dups(text, pk=pk, biz_key=biz_key)
    actions: list[RepairAction] = []

    # ── dedup actions (one per layer that fired) ─────────────────────
    if dups.row_dup_rows:
        actions.append(RepairAction(
            "dedup", "high", "", {
                "layer": "row", "extra_rows": dups.row_dup_rows},
            _dedup_sql(table, [], headers)))
    if dups.pk_dup_rows:
        actions.append(RepairAction(
            "dedup", "high", "", {
                "layer": "pk", "extra_rows": dups.pk_dup_rows,
                "keys": dups.pk_columns},
            _dedup_sql(table, dups.pk_columns, headers)))
    if dups.biz_dup_rows:
        actions.append(RepairAction(
            "dedup", "mid", "", {
                "layer": "biz", "extra_rows": dups.biz_dup_rows,
                "keys": dups.biz_columns},
            _dedup_sql(table, dups.biz_columns, headers)))

    # ── column repairs from the profile findings ─────────────────────
    for f in profile.findings:
        col = f.column
        if f.code == "SP002":           # high nulls -> backfill choices
            actions.append(RepairAction(
                "null_backfill", "mid", col,
                {"null_pct": f.detail["null_pct"],
                 "strategies": ["default", "forward_fill",
                                "upstream_rerun"]},
                f"-- choose ONE strategy:\n"
                f"-- (1) default value\n"
                f"UPDATE {table} SET {col} = COALESCE({col}, "
                f"<default_value>)\nWHERE {col} IS NULL;\n"
                f"-- (2) forward fill from the previous row "
                f"(needs an order column)\n"
                f"INSERT OVERWRITE TABLE {table}\n"
                f"SELECT /* other columns, */ COALESCE({col}, LAST_VALUE("
                f"{col}, TRUE)\n"
                f"  OVER (ORDER BY <order_col> ROWS BETWEEN UNBOUNDED "
                f"PRECEDING AND CURRENT ROW)) AS {col}\n"
                f"FROM {table};\n"
                f"-- (3) upstream re-run: backfill the source partition, "
                f"then re-run this table's job"))
        elif f.code == "SP006":         # whitespace / case drift
            variants = f.detail.get("variants", {})
            actions.append(RepairAction(
                "standardize", "mid", col, {"variants": variants},
                f"UPDATE {table}\n"
                f"SET {col} = LOWER(TRIM({col}))\n"
                f"WHERE {col} <> LOWER(TRIM({col}));"))
        elif f.code == "SP005":         # numeric stored as text
            actions.append(RepairAction(
                "numeric_cast", "mid", col,
                {"examples": f.detail.get("examples", [])},
                f"-- strip grouping separators and currency marks, then "
                f"cast\n"
                f"UPDATE {table}\n"
                f"SET {col} = CAST(REPLACE(REPLACE({col}, ',', ''), "
                f"'¥', '') AS DECIMAL(18,2));"))
        elif f.code == "SP004":         # outlier formats
            dominant = f.detail.get("dominant", "")
            examples = f.detail.get("examples", [])
            rows_hint = ", ".join(str(e["row"]) for e in examples) or "-"
            actions.append(RepairAction(
                "format_fix", "mid", col,
                {"dominant": dominant, "rows": rows_hint,
                 "examples": examples},
                f"-- rewrite the stragglers into the dominant "
                f"'{dominant}' format\n"
                f"UPDATE {table}\n"
                f"SET {col} = <convert_to_{dominant}>({col})\n"
                f"WHERE {col} IS NOT NULL AND NOT "
                f"<matches_{dominant}>({col});"))
        elif f.code == "SP001":         # mixed types: needs a decision
            actions.append(RepairAction(
                "format_fix", "high", col,
                {"buckets": f.detail.get("buckets", {})},
                f"-- the column mixes value kinds; pick the target type "
                f"first, then:\n"
                f"UPDATE {table}\n"
                f"SET {col} = <normalize>({col});"))

    order = {"high": 0, "mid": 1, "low": 2}
    kind_order = {"dedup": 0, "format_fix": 1, "numeric_cast": 2,
                  "standardize": 3, "null_backfill": 4}
    actions.sort(key=lambda a: (order[a.severity], kind_order[a.kind],
                                a.column))
    return RepairPlan(table=table, total_rows=len(rows), actions=actions)
