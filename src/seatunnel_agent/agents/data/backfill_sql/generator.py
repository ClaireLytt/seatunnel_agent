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

MODES = ("overwrite", "delete_insert", "merge", "overwrite_dynamic")
DIALECTS = ("hive", "spark", "mysql", "doris")
RUNNERS = {
    "spark-sql": 'spark-sql -e "$SQL"',
    "beeline": 'beeline -u "$JDBC_URL" -e "$SQL"',
    "hive": 'hive -e "$SQL"',
    "mysql": 'mysql --defaults-extra-file="$MYSQL_CNF" -e "$SQL"',
}
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
    dates: list[date] = field(default_factory=list)  # explicit slots
    # (overrides the start..end grid; day grain only)
    runner: str = ""                  # optional: emit a bash runner script


def parse_spec(text: str) -> BackfillSpec:
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("empty spec")
    data = json.loads(stripped)
    if not isinstance(data, dict):
        raise ValueError("spec must be a JSON object")
    explicit_dates = data.get("dates") or []
    if explicit_dates:
        if not isinstance(explicit_dates, list):
            raise ValueError("'dates' must be a list of ISO dates")
        try:
            parsed_dates = sorted({date.fromisoformat(str(d).strip())
                                   for d in explicit_dates})
        except ValueError as exc:
            raise ValueError(f"'dates' must be ISO dates: {exc}") from exc
        if len(parsed_dates) > MAX_DAYS:
            raise ValueError(f"'dates' exceeds {MAX_DAYS} slots — "
                             f"split the backfill")
        data = {**data, "start": parsed_dates[0].isoformat(),
                "end": parsed_dates[-1].isoformat()}
    else:
        parsed_dates = []
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
    if parsed_dates and grain == "hour":
        raise ValueError("'dates' list works with day grain only")
    mode = str(data.get("mode") or "overwrite").strip().lower()
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    dialect = str(data.get("dialect") or "hive").strip().lower()
    if dialect not in DIALECTS:
        raise ValueError(f"dialect must be one of {DIALECTS}")
    source = str(data["source"]).strip().rstrip(";")
    if mode == "overwrite_dynamic":
        if "{start}" not in source or "{end}" not in source:
            raise ValueError(
                "mode 'overwrite_dynamic' needs {start} and {end} "
                "placeholders in the source SELECT — unbounded reads "
                "are not allowed")
        if dialect not in ("spark", "hive"):
            raise ValueError(
                "mode 'overwrite_dynamic' is for spark/hive only")
        if grain == "hour" or explicit_dates:
            raise ValueError(
                "mode 'overwrite_dynamic' works on a contiguous day "
                "range (no 'dates' list, no hourly grain)")
    elif "{date}" not in source:
        raise ValueError(
            "source SELECT must contain the {date} placeholder — "
            "unbounded backfill reads are not allowed")
    keys = [str(k).strip() for k in (data.get("keys") or []) if str(k).strip()]
    if mode == "merge" and not keys:
        raise ValueError("mode 'merge' requires 'keys'")
    source_table = str(data.get("source_table") or "").strip()
    if source_table and not _IDENT_RE.match(source_table):
        raise ValueError(f"bad identifier: {source_table!r}")
    runner = str(data.get("runner") or "").strip().lower()
    if runner and runner not in RUNNERS:
        raise ValueError(f"runner must be one of {tuple(RUNNERS)}")
    return BackfillSpec(
        table=table, partition_col=partition_col, start=start, end=end,
        source=source, mode=mode, dialect=dialect,
        date_format=date_format, grain=grain,
        keys=keys, source_table=source_table, dates=parsed_dates,
        runner=runner)


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
    postchecks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    runner_script: str = ""  # stop-on-fail bash wrapping every block

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "mode": self.mode,
                "dialect": self.dialect,
                "dates": [d.to_dict() for d in self.dates],
                "prechecks": list(self.prechecks),
                "postchecks": list(self.postchecks),
                "warnings": list(self.warnings),
                "runner_script": self.runner_script}


def _generate_dynamic(spec: BackfillSpec, result: BackfillSql,
                      strf: str) -> BackfillSql:
    """One dynamic-partition statement covering the whole day range."""
    first = spec.start.strftime(strf)
    last = spec.end.strftime(strf)
    source = spec.source.replace("{start}", first).replace("{end}", last)
    setting = ("SET hive.exec.dynamic.partition.mode = nonstrict;"
               if spec.dialect == "hive" else
               "SET spark.sql.sources.partitionOverwriteMode = dynamic;")
    if spec.dialect == "hive":
        result.warnings.append(
            "hive: dynamic-partition overwrite replaces only the "
            "partitions present in the SELECT — verify "
            "hive.exec.dynamic.partition.mode=nonstrict is allowed")
    stmt = (f"{setting}\n"
            f"INSERT OVERWRITE TABLE {spec.table} "
            f"PARTITION ({spec.partition_col})\n{source};")
    result.dates.append(DateStatements(
        date=f"{spec.start.isoformat()}..{spec.end.isoformat()}",
        partition_value=f"{first}..{last}", statements=[stmt]))
    _add_checks(spec, result, first, last)
    return result


def _add_checks(spec: BackfillSpec, result: BackfillSql,
                first: str, last: str) -> None:
    """Target/source row counts up front, reconciliation for afterwards."""
    col = spec.partition_col
    bound = f"{col} BETWEEN '{first}' AND '{last}'"
    result.prechecks.append(
        f"SELECT {col}, COUNT(*) AS target_rows\n"
        f"FROM {spec.table}\nWHERE {bound}\n"
        f"GROUP BY {col} ORDER BY 1;")
    if not spec.source_table:
        return
    result.prechecks.append(
        f"SELECT {col}, COUNT(*) AS source_rows\n"
        f"FROM {spec.source_table}\nWHERE {bound}\n"
        f"GROUP BY {col} ORDER BY 1;")
    result.postchecks.append(
        f"SELECT COALESCE(s.{col}, t.{col}) AS {col},\n"
        f"       s.source_rows, t.target_rows\n"
        f"FROM (SELECT {col}, COUNT(*) AS source_rows\n"
        f"      FROM {spec.source_table} WHERE {bound}\n"
        f"      GROUP BY {col}) s\n"
        f"FULL OUTER JOIN\n"
        f"     (SELECT {col}, COUNT(*) AS target_rows\n"
        f"      FROM {spec.table} WHERE {bound}\n"
        f"      GROUP BY {col}) t\n"
        f"ON s.{col} = t.{col}\n"
        f"WHERE COALESCE(s.source_rows, -1) <> "
        f"COALESCE(t.target_rows, -1)\n"
        f"ORDER BY 1;")


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
    if spec.mode == "overwrite_dynamic":
        _generate_dynamic(spec, result, strf)
        if spec.runner:
            result.runner_script = _runner_script(spec, result)
        return result
    if spec.dates:
        slots = [datetime.combine(d, datetime.min.time())
                 for d in spec.dates]
    else:
        slots = []
        slot = datetime.combine(spec.start, datetime.min.time())
        stop = datetime.combine(spec.end, datetime.min.time())
        if spec.grain == "hour":
            stop += timedelta(hours=23)
            step = timedelta(hours=1)
        else:
            step = timedelta(days=1)
        while slot <= stop:
            slots.append(slot)
            slot += step
    for slot in slots:
        pv = slot.strftime(strf)
        source = spec.source.replace("{date}", pv)
        label = slot.date().isoformat() if spec.grain == "day" \
            else slot.isoformat(timespec="hours")
        result.dates.append(DateStatements(
            date=label, partition_value=pv,
            statements=_statements(spec, pv, source)))
    _add_checks(spec, result, result.dates[0].partition_value,
                result.dates[-1].partition_value)
    if spec.runner:
        result.runner_script = _runner_script(spec, result)
    return result


def _runner_script(spec: BackfillSpec, result: BackfillSql) -> str:
    """Stop-on-fail bash wrapping every statement block, heredoc-quoted."""
    lines = ["#!/usr/bin/env bash",
             f"# backfill {spec.table} — generated, review before running",
             "set -euo pipefail", ""]
    cmd = RUNNERS[spec.runner]
    for block in result.dates:
        lines.append(f"echo '>>> {spec.table} {block.date}'")
        lines.append('SQL="$(cat <<\'ST_BACKFILL_SQL\'')
        lines.extend(block.statements)
        lines.append("ST_BACKFILL_SQL")
        lines.append(')"')
        lines.append(cmd)
        lines.append("")
    lines.append(f"echo 'done: {len(result.dates)} block(s)'")
    return "\n".join(lines)
