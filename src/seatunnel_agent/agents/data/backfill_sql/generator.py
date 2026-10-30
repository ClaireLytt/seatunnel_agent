"""Deterministic safe-backfill SQL generator.

Input: a JSON spec — target table, partition column, business date
range, source SELECT (with a ``{date}`` placeholder), write mode and
dialect.  Output: one idempotent, partition-bounded statement block per
business date plus pre-flight check SQL (source/target row counts per
partition).

Safety rules enforced:
* the source SELECT must carry the ``{date}`` placeholder, so every
  statement is bounded to a single partition;
* the date range is capped (366 days) to stop runaway backfills;
* ``merge`` requires the business keys;
* every write targets exactly one partition — idempotent to re-run.

No database connection — the SQL is generated, never executed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

MODES = ("overwrite", "delete_insert", "merge")
DIALECTS = ("hive", "spark", "mysql", "doris")
GRAINS = ("day", "hour")
MAX_DAYS = 366
MAX_HOUR_DAYS = 31          # hourly grain: cap the range tighter

_FMT_TOKENS = (("yyyy", "%Y"), ("MM", "%m"), ("dd", "%d"), ("HH", "%H"))
_IDENT_RE = re.compile(r"^[\w.]+$")


def _to_strftime(fmt: str) -> str:
    out = fmt or "yyyy-MM-dd"
    for token, strf in _FMT_TOKENS:
        out = out.replace(token, strf)
    if "%" not in out:
        raise ValueError(f"unsupported date format: {fmt!r}")
    return out


@dataclass
class BackfillSpec:
    table: str
    partition_col: str
    start: date
    end: date
    source: str                       # SELECT with {date}
    mode: str = "overwrite"
    dialect: str = "hive"
    date_format: str = "yyyy-MM-dd"
    grain: str = "day"                # "day" | "hour" (one slot per hour)
    keys: list[str] = field(default_factory=list)  # merge only
    source_table: str = ""            # for pre-flight counts (optional)


def parse_spec(text: str) -> BackfillSpec:
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("empty spec")
    data = json.loads(stripped)
    if not isinstance(data, dict):
        raise ValueError("spec must be a JSON object")
    missing = [k for k in ("table", "partition_col", "start", "end", "source")
               if not str(data.get(k) or "").strip()]
    if missing:
        raise ValueError(f"missing field(s): {', '.join(missing)}")
    table = str(data["table"]).strip()
    partition_col = str(data["partition_col"]).strip()
    for ident in (table, partition_col):
        if not _IDENT_RE.match(ident):
            raise ValueError(f"bad identifier: {ident!r}")
    try:
        start = date.fromisoformat(str(data["start"]).strip())
        end = date.fromisoformat(str(data["end"]).strip())
    except ValueError as exc:
        raise ValueError(f"start/end must be ISO dates: {exc}") from exc
    if end < start:
        raise ValueError("end date before start date")
    date_format = str(data.get("date_format") or "yyyy-MM-dd")
    grain = str(data.get("grain") or
                ("hour" if "HH" in date_format else "day")).strip().lower()
    if grain not in GRAINS:
        raise ValueError(f"grain must be one of {GRAINS}")
    days = (end - start).days + 1
    if grain == "day" and days > MAX_DAYS:
        raise ValueError(f"range exceeds {MAX_DAYS} days — split the backfill")
    if grain == "hour" and days > MAX_HOUR_DAYS:
        raise ValueError(f"hourly range exceeds {MAX_HOUR_DAYS} days — "
                         f"split the backfill")
    if grain == "hour" and "HH" not in date_format:
        raise ValueError("hourly grain needs 'HH' in date_format")
    mode = str(data.get("mode") or "overwrite").strip().lower()
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    dialect = str(data.get("dialect") or "hive").strip().lower()
    if dialect not in DIALECTS:
        raise ValueError(f"dialect must be one of {DIALECTS}")
    source = str(data["source"]).strip().rstrip(";")
    if "{date}" not in source:
        raise ValueError(
            "source SELECT must contain the {date} placeholder — "
            "unbounded backfill reads are not allowed")
    keys = [str(k).strip() for k in (data.get("keys") or []) if str(k).strip()]
    if mode == "merge" and not keys:
        raise ValueError("mode 'merge' requires 'keys'")
    source_table = str(data.get("source_table") or "").strip()
    if source_table and not _IDENT_RE.match(source_table):
        raise ValueError(f"bad identifier: {source_table!r}")
    return BackfillSpec(
        table=table, partition_col=partition_col, start=start, end=end,
        source=source, mode=mode, dialect=dialect,
        date_format=date_format, grain=grain,
        keys=keys, source_table=source_table)


@dataclass
class DateStatements:
    date: str                 # business date, ISO
    partition_value: str      # formatted for the partition column
    statements: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"date": self.date, "partition_value": self.partition_value,
                "statements": list(self.statements)}


@dataclass
class BackfillSql:
    table: str
    mode: str
    dialect: str
    dates: list[DateStatements] = field(default_factory=list)
    prechecks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "mode": self.mode,
                "dialect": self.dialect,
                "dates": [d.to_dict() for d in self.dates],
                "prechecks": list(self.prechecks),
                "warnings": list(self.warnings)}


def _statements(spec: BackfillSpec, pv: str, source: str) -> list[str]:
    t, col = spec.table, spec.partition_col
    if spec.mode == "overwrite":
        if spec.dialect in ("hive", "spark"):
            return [f"INSERT OVERWRITE TABLE {t} "
                    f"PARTITION ({col} = '{pv}')\n{source};"]
        # mysql/doris: no INSERT OVERWRITE — fall back to delete + insert
        return _delete_insert(spec, pv, source)
    if spec.mode == "delete_insert":
        return _delete_insert(spec, pv, source)
    on = " AND ".join(f"t.{k} = s.{k}" for k in spec.keys)
    return [f"MERGE INTO {t} AS t\nUSING (\n{source}\n) AS s\n"
            f"ON {on} AND t.{col} = '{pv}'\n"
            f"WHEN MATCHED THEN UPDATE SET *\n"
            f"WHEN NOT MATCHED THEN INSERT *;"]


def _delete_insert(spec: BackfillSpec, pv: str, source: str) -> list[str]:
    t, col = spec.table, spec.partition_col
    return [f"DELETE FROM {t} WHERE {col} = '{pv}';",
            f"INSERT INTO {t}\n{source};"]


def generate(spec: BackfillSpec) -> BackfillSql:
    result = BackfillSql(table=spec.table, mode=spec.mode,
                         dialect=spec.dialect)
    strf = _to_strftime(spec.date_format)
    if spec.mode == "overwrite" and spec.dialect in ("mysql", "doris"):
        result.warnings.append(
            f"{spec.dialect}: no INSERT OVERWRITE — generated "
            "DELETE + INSERT per partition instead")
    if spec.mode == "merge" and spec.dialect in ("hive", "mysql"):
        result.warnings.append(
            f"{spec.dialect}: MERGE needs engine support "
            "(Hive ACID / MySQL has none) — verify before running")
    slot = datetime.combine(spec.start, datetime.min.time())
    stop = datetime.combine(spec.end, datetime.min.time())
    if spec.grain == "hour":
        stop += timedelta(hours=23)
        step = timedelta(hours=1)
    else:
        step = timedelta(days=1)
    while slot <= stop:
        pv = slot.strftime(strf)
        source = spec.source.replace("{date}", pv)
        label = slot.date().isoformat() if spec.grain == "day" \
            else slot.isoformat(timespec="hours")
        result.dates.append(DateStatements(
            date=label, partition_value=pv,
            statements=_statements(spec, pv, source)))
        slot += step
    first = result.dates[0].partition_value
    last = result.dates[-1].partition_value
    bound = (f"{spec.partition_col} BETWEEN '{first}' AND '{last}'")
    result.prechecks.append(
        f"SELECT {spec.partition_col}, COUNT(*) AS target_rows\n"
        f"FROM {spec.table}\nWHERE {bound}\n"
        f"GROUP BY {spec.partition_col} ORDER BY 1;")
    if spec.source_table:
        result.prechecks.append(
            f"SELECT {spec.partition_col}, COUNT(*) AS source_rows\n"
            f"FROM {spec.source_table}\nWHERE {bound}\n"
            f"GROUP BY {spec.partition_col} ORDER BY 1;")
    return result
