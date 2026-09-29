# -*- coding: utf-8 -*-
"""SeaTunnel split-key check: measure the parallel-read partition column.

Static skew rules cover the compute layer; this module covers the sync /
ingest layer. Given a SeaTunnel job config (HOCON), it resolves the JDBC
source's base table and ``partition_column``, measures that column's
distribution on the connected database (NDV / NULL ratio / top-1 share,
one bounded scan per query, sampling honored), and ranks candidate
numeric/date columns as replacement split keys — a skewed split key means
one read task drags the whole sync job.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .i18n import dsk, normalize_lang
from .probe import (
    HOT_KEY_CONFIRMED,
    HOT_KEY_SUSPECT,
    NULL_CONFIRMED,
    _pct,
    _safe_value,
    _table_expr,
)

MAX_CANDIDATES = 5
MAX_PARALLEL = 4
# a split key should hold clearly more distinct values than read tasks,
# or range/hash splits collapse onto few tasks
NDV_PER_TASK = 4

_IDENT = r"[A-Za-z_][\w$]*"
_TABLE_RE = re.compile(rf"^{_IDENT}(\.{_IDENT})?$")
# single-table FROM in a source query (subqueries/joins are out of scope)
_QUERY_FROM_RE = re.compile(
    rf"\bfrom\s+({_IDENT}(?:\.{_IDENT})?)\s*(?:$|;|\bwhere\b|\blimit\b)",
    re.IGNORECASE,
)
# column types worth proposing as split keys: integers, decimals, dates
_CANDIDATE_TYPE_RE = re.compile(
    r"int|serial|number|decimal|numeric|double|float|real|date|time",
    re.IGNORECASE,
)


@dataclass
class SourceSpec:
    """The parsed JDBC-ish source block of a SeaTunnel job config."""
    plugin: str = ""
    table: str = ""
    partition_column: str = ""
    partition_num: int = 0
    parallelism: int = 0

    @property
    def tasks(self) -> int:
        """Effective parallel read tasks the split key must feed."""
        return max(self.partition_num, self.parallelism, 2)


@dataclass
class SplitStat:
    column: str
    total: int = 0
    ndv: int = 0
    null_count: int = 0
    top1_value: str = ""
    top1_count: int = 0
    elapsed_ms: int = 0
    error: str = ""

    @property
    def null_ratio(self) -> float:
        return self.null_count / self.total if self.total else 0.0

    @property
    def top1_ratio(self) -> float:
        return self.top1_count / self.total if self.total else 0.0

    def verdict(self, tasks: int) -> str:
        """'good' | 'suspect' | 'bad' | 'low_ndv' | 'null' | 'error' | 'empty'."""
        if self.error:
            return "error"
        if not self.total:
            return "empty"
        if self.null_ratio >= NULL_CONFIRMED:
            return "null"
        if self.ndv < NDV_PER_TASK * tasks:
            return "low_ndv"
        if self.top1_ratio >= HOT_KEY_CONFIRMED:
            return "bad"
        if self.top1_ratio >= HOT_KEY_SUSPECT:
            return "suspect"
        return "good"


class SplitKeyError(ValueError):
    """Config-level failure; ``key`` is the i18n message key, ``arg`` the
    optional {err} detail."""

    def __init__(self, key: str, arg: str = "") -> None:
        super().__init__(key)
        self.key = key
        self.arg = arg


def parse_seatunnel_source(conf_text: str) -> SourceSpec:
    """Resolve the first source plugin's base table + split settings.

    Accepts both source shapes: ``source { Jdbc { … } }`` and the list form
    ``source = [{ plugin_name = "Jdbc", … }]``.  Understands the JDBC
    options (``table_path`` / ``table_name`` / ``partition_column``) and the
    CDC connectors' hyphenated ones (``database-name(s)`` /
    ``table-name(s)``, list options take the first entry, and the
    incremental-snapshot split key
    ``scan.incremental.snapshot.chunk.key-column``).
    """
    try:
        from pyhocon import ConfigFactory
    except ImportError as exc:  # pragma: no cover — dependency of the app
        raise SplitKeyError("spk_parse_fail", f"pyhocon not installed: {exc}")
    try:
        conf = ConfigFactory.parse_string(conf_text)
    except Exception as exc:  # noqa: BLE001 — HOCON syntax error
        raise SplitKeyError("spk_parse_fail", str(exc))

    source = conf.get("source", None)
    plugin, params = "", None
    if isinstance(source, list):
        for item in source:
            if hasattr(item, "get"):
                plugin = str(item.get("plugin_name", "") or "Jdbc")
                params = item
                break
    elif source is not None and hasattr(source, "items"):
        for name, block in source.items():
            if hasattr(block, "get"):
                plugin, params = str(name), block
                break
    if params is None:
        raise SplitKeyError("spk_no_source")

    def _get(key: str, default: str = "") -> str:
        v = params.get(key, default)
        if isinstance(v, (list, tuple)):  # CDC list options: first entry
            v = v[0] if v else default
        return str(v).strip() if v is not None else default

    def _get_any(*keys: str) -> str:
        for key in keys:
            v = _get(key)
            if v:
                return v
        return ""

    # JDBC snake_case options first, then the CDC connectors' hyphenated
    # ones (MySQL-CDC & co.; table-names entries are usually db-qualified)
    table = _get_any("table_path", "table_name", "table",
                     "table-name", "table-names")
    if not table:
        query = _get("query")
        m = _QUERY_FROM_RE.search(query) if query else None
        if m:
            table = m.group(1)
    if table and "." not in table:
        # CDC splits database and table into separate options
        db = _get_any("database-name", "database-names", "database_name")
        if db:
            table = f"{db}.{table}"
    if not table or not _TABLE_RE.match(table):
        raise SplitKeyError("spk_no_table")

    def _int(key: str) -> int:
        try:
            return int(str(params.get(key, 0) or 0))
        except (TypeError, ValueError):
            return 0

    env = conf.get("env", None)
    parallelism = 0
    if env is not None and hasattr(env, "get"):
        try:
            parallelism = int(str(env.get("parallelism", 0) or 0))
        except (TypeError, ValueError):
            parallelism = 0

    return SourceSpec(
        plugin=plugin,
        table=table,
        # CDC jobs split the snapshot by chunk key-column, not
        # partition_column — both are "the column parallel reads split on"
        partition_column=_get_any(
            "partition_column", "scan.incremental.snapshot.chunk.key-column"),
        partition_num=_int("partition_num"),
        parallelism=parallelism,
    )


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

# Approximate-NDV function per engine: an exact COUNT(DISTINCT) on a big
# table is the most expensive part of the check, and the NDV only feeds a
# threshold (>= NDV_PER_TASK * tasks), so a few % of HLL error is free money.
_APPROX_NDV: dict[str, str] = {
    "sparksql": "approx_count_distinct({col})",
    "clickhouse": "uniq({col})",
    "doris": "ndv({col})",
}


def _ndv_expr(column: str, ds_type: str) -> str:
    tpl = _APPROX_NDV.get(ds_type)
    return tpl.format(col=column) if tpl else f"COUNT(DISTINCT {column})"


def _stats_sql(column: str, table_expr: str, ds_type: str = "") -> str:
    return (
        f"SELECT COUNT(*) AS total, {_ndv_expr(column, ds_type)} AS ndv, "
        f"SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END) AS nulls "
        f"FROM {table_expr}"
    )


def _top1_sql(column: str, table_expr: str) -> str:
    return (
        f"SELECT {column} AS k, COUNT(*) AS cnt FROM {table_expr} "
        f"WHERE {column} IS NOT NULL "
        f"GROUP BY {column} ORDER BY cnt DESC LIMIT 1"
    )


def measure_column(executor, table: str, column: str,
                   ds_type: str = "", sample_pct: int = 0) -> SplitStat:
    """Two bounded scans: totals/NDV/NULLs, then the top-1 non-NULL value."""
    s = SplitStat(column=column)
    expr = _table_expr(table, ds_type, sample_pct)
    try:
        rq = executor.run(_stats_sql(column, expr, ds_type), max_rows=1)
        s.total = int(rq.rows[0][0] or 0)
        s.ndv = int(rq.rows[0][1] or 0)
        s.null_count = int(rq.rows[0][2] or 0)
        s.elapsed_ms += rq.elapsed_ms
        if s.total:
            tq = executor.run(_top1_sql(column, expr), max_rows=1)
            if tq.rows:
                s.top1_value = "NULL" if tq.rows[0][0] is None else str(tq.rows[0][0])
                s.top1_count = int(tq.rows[0][1] or 0)
            s.elapsed_ms += tq.elapsed_ms
    except Exception as exc:  # noqa: BLE001 — per-column failure stays local
        s.error = str(exc)
    return s


def candidate_columns(executor, table: str, exclude: str = "") -> list[str]:
    """Numeric/date columns of *table*, config order, configured key excluded."""
    schema = executor.describe_table(table)
    out: list[str] = []
    for col in schema.columns:
        if col.name.lower() == exclude.lower():
            continue
        if _CANDIDATE_TYPE_RE.search(col.dtype or ""):
            out.append(col.name)
        if len(out) >= MAX_CANDIDATES:
            break
    return out


def measure_columns(executor, table: str, columns: list[str],
                    ds_type: str = "", sample_pct: int = 0) -> list[SplitStat]:
    if not columns:
        return []
    if len(columns) == 1:
        return [measure_column(executor, table, columns[0], ds_type, sample_pct)]
    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(columns))) as pool:
        return list(pool.map(
            lambda c: measure_column(executor, table, c, ds_type, sample_pct),
            columns))


_VERDICT_RANK = {"good": 0, "suspect": 1, "low_ndv": 2, "null": 2,
                 "bad": 3, "empty": 4, "error": 5}


def rank_candidates(stats: list[SplitStat], tasks: int) -> list[SplitStat]:
    """Best split key first: verdict class, then top-1 share, then NDV."""
    return sorted(stats, key=lambda s: (
        _VERDICT_RANK.get(s.verdict(tasks), 5), s.top1_ratio, -s.ndv))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _stat_row(s: SplitStat, tasks: int, lang: str) -> str:
    verdict = dsk(lang, f"spk_verdict_{s.verdict(tasks)}") \
        if s.verdict(tasks) != "empty" else dsk(lang, "prb_verdict_empty")
    if s.error:
        err = s.error.replace("|", "\\|").replace("\n", " ")
        err = err if len(err) <= 80 else err[:79] + "…"
        return f"| `{s.column}` | - | - | - | {err} | {verdict} |"
    top1 = (f"`{_safe_value(s.top1_value)}` ({_pct(s.top1_ratio)})"
            if s.top1_count else "-")
    return (f"| `{s.column}` | {s.total} | {s.ndv} | "
            f"{_pct(s.null_ratio)} | {top1} | {verdict} |")


def render_splitkey_section(
    spec: SourceSpec,
    configured: SplitStat | None,
    candidates: list[SplitStat],
    lang: str,
    sample_pct: int = 0,
) -> str:
    """Bilingual '## SeaTunnel 分片键体检（实测）' markdown section."""
    lang = normalize_lang(lang)
    zh = lang == "zh"
    tasks = spec.tasks
    parts = [dsk(lang, "spk_section"), ""]
    src_line = (f"source `{spec.plugin}` → 表 `{spec.table}`，并行度 {tasks}"
                if zh else
                f"source `{spec.plugin}` → table `{spec.table}`, parallelism {tasks}")
    if sample_pct:
        src_line += " " + dsk(lang, "spk_sampled_note").format(pct=sample_pct)
    parts += [src_line, ""]

    header = (
        f"| {dsk(lang, 'spk_col_column')} | {dsk(lang, 'spk_col_rows')} | "
        f"{dsk(lang, 'spk_col_ndv')} | {dsk(lang, 'spk_col_null')} | "
        f"{dsk(lang, 'spk_col_top1')} | {dsk(lang, 'spk_col_verdict')} |"
    )
    sep = "|---|---|---|---|---|---|"

    if configured is not None:
        parts += [dsk(lang, "spk_configured") + f": `{spec.partition_column}`", "",
                  header, sep, _stat_row(configured, tasks, lang), ""]
    else:
        parts += [dsk(lang, "spk_none_configured"), ""]

    ranked = rank_candidates(candidates, tasks) if candidates else []
    if ranked:
        parts += [dsk(lang, "spk_candidates"), "", header, sep]
        parts += [_stat_row(s, tasks, lang) for s in ranked]
        parts.append("")
    elif configured is None:
        parts += [dsk(lang, "spk_no_candidates"), ""]

    # config snippet: keep a good configured key, else promote the best
    # measured candidate
    best: SplitStat | None = None
    if configured is not None and configured.verdict(tasks) in ("good", "suspect"):
        best = configured
    elif ranked and ranked[0].verdict(tasks) in ("good", "suspect"):
        best = ranked[0]
    if best is not None:
        note = ("实测 top1≈{p}，NDV={n}" if zh else "measured top1≈{p}, NDV={n}").format(
            p=_pct(best.top1_ratio), n=best.ndv)
        parts += [
            dsk(lang, "spk_snippet_head"), "",
            "```hocon",
            f"{spec.plugin or 'Jdbc'} {{",
            f"  # {note}",
            f'  partition_column = "{best.column}"',
            f"  partition_num = {max(spec.partition_num, tasks)}",
            "}",
            "```", "",
        ]
    parts += [dsk(lang, "spk_sink_note"), ""]
    return "\n".join(parts)


def run_split_key(
    executor,
    conf_text: str,
    ds_type: str = "",
    sample_pct: int = 0,
) -> tuple[SourceSpec, SplitStat | None, list[SplitStat]]:
    """Parse the config and measure everything; the structured half of
    :func:`check_split_key`. Raises SplitKeyError on config problems."""
    spec = parse_seatunnel_source(conf_text)
    configured = None
    if spec.partition_column:
        configured = measure_column(
            executor, spec.table, spec.partition_column, ds_type, sample_pct)
    try:
        names = candidate_columns(executor, spec.table, exclude=spec.partition_column)
    except Exception:  # noqa: BLE001 — schema listing is best-effort
        names = []
    candidates = measure_columns(executor, spec.table, names, ds_type, sample_pct)
    return spec, configured, candidates


def check_split_key(
    executor,
    conf_text: str,
    ds_type: str = "",
    sample_pct: int = 0,
    lang: str = "zh",
) -> str:
    """Parse → measure → render. Raises SplitKeyError on config problems."""
    spec, configured, candidates = run_split_key(
        executor, conf_text, ds_type=ds_type, sample_pct=sample_pct)
    return render_splitkey_section(spec, configured, candidates, lang, sample_pct)
