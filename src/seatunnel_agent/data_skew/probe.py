# -*- coding: utf-8 -*-
"""Optional runtime skew verification against a live database.

Static rules only *suspect* skew; when the user connects a datasource
(Hive / Spark SQL / MySQL / ...), lightweight probe queries measure the
actual distribution: hot-key Top-N, NULL ratio, and table row count.

Probes only touch base tables parsed from the script's FROM / JOIN
clauses — subquery aliases and expressions are skipped — and every probe
is a single bounded aggregate (GROUP BY ... LIMIT N), so the cost per
target is one scan of that table.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .detector import clean_sql, split_statements
from .i18n import dsk, normalize_lang

MAX_TARGETS = 8
TOP_N = 10

# Verdict thresholds (share of total rows)
HOT_KEY_CONFIRMED = 0.20
HOT_KEY_SUSPECT = 0.05
NULL_CONFIRMED = 0.10

_IDENT_RE = re.compile(r"^[A-Za-z_][\w]*(\.[A-Za-z_][\w]*)?$")

_RESERVED = frozenset(
    "select from where join on using group order by having limit union all "
    "distinct left right full inner cross outer semi anti lateral as and or "
    "not in exists case when then else end insert overwrite into table "
    "partition values with sort distribute cluster".split()
)

# The alias group must not swallow a following keyword (e.g. the JOIN in
# "FROM orders JOIN users"), or the next table would never be matched.
_KW_GUARD = (
    r"(?!(?:join|left|right|full|inner|cross|outer|semi|anti|lateral|on|using|"
    r"where|group|order|union|having|limit|sort|distribute|cluster)\b)"
)
_FROM_JOIN_RE = re.compile(
    r"\b(?:from|join)\s+([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)?)"
    rf"(?:\s+(?:as\s+)?{_KW_GUARD}([A-Za-z_][\w]*))?",
    re.IGNORECASE,
)

_ON_RE = re.compile(r"\bon\b", re.IGNORECASE)
_CLAUSE_END_RE = re.compile(
    r"\b(?:where|join|left|right|full|inner|cross|group|order|union|having|limit|select)\b|;",
    re.IGNORECASE,
)
_EQ_QUALIFIED_RE = re.compile(r"([A-Za-z_]\w*)\.([A-Za-z_]\w*)\s*=\s*([A-Za-z_]\w*)\.([A-Za-z_]\w*)")
_CD_COL_RE = re.compile(
    r"\bcount\s*\(\s*distinct\s+(?:([A-Za-z_]\w*)\.)?([A-Za-z_]\w*)\s*\)",
    re.IGNORECASE,
)
_GROUP_BY_RE = re.compile(r"\bgroup\s+by\s+", re.IGNORECASE)
# A ')' also ends the clause so a subquery's GROUP BY never leaks columns
# into the outer scope.
_GROUP_END_RE = re.compile(r"\b(?:having|order|limit|union|window|qualify)\b|[;)]",
                           re.IGNORECASE)
# GROUPING SETS / ROLLUP / CUBE arguments and Spark's GROUP BY ALL are not
# plain columns.
_GROUP_SKIP = frozenset({"all", "grouping", "sets", "rollup", "cube"})
_PLAIN_COL_RE = re.compile(r"(?:([A-Za-z_]\w*)\.)?([A-Za-z_]\w*)")


@dataclass
class ProbeTarget:
    table: str    # resolved base table, possibly db-qualified
    column: str   # bare column name
    reason: str   # "join_key" | "count_distinct"


@dataclass
class ProbeResult:
    target: ProbeTarget
    total: int = 0
    null_count: int = 0
    top: list[tuple[str, int]] = field(default_factory=list)  # (value, count) desc
    elapsed_ms: int = 0
    error: str = ""

    @property
    def null_ratio(self) -> float:
        return self.null_count / self.total if self.total else 0.0

    @property
    def top1_ratio(self) -> float:
        return self.top[0][1] / self.total if self.top and self.total else 0.0

    @property
    def verdict(self) -> str:
        """'error' | 'empty' | 'confirmed' | 'suspect' | 'ok'."""
        if self.error:
            return "error"
        if self.total == 0:
            return "empty"
        if self.null_ratio >= NULL_CONFIRMED or self.top1_ratio >= HOT_KEY_CONFIRMED:
            return "confirmed"
        if self.top1_ratio >= HOT_KEY_SUSPECT:
            return "suspect"
        return "ok"


# CTE definitions: "name AS (" (optionally with a column list). A CTE is not
# a physical table, so FROM/JOIN references to it must never become probe
# targets — probing would hit an unrelated real table of the same name (or
# fail outright).
_CTE_RE = re.compile(
    r"\b([A-Za-z_]\w*)\s*(?:\([^()]*\)\s*)?\bas\s*\(", re.IGNORECASE
)


def _alias_map(cleaned_stmt: str) -> dict[str, str]:
    """alias (or bare table name) -> base table, from FROM/JOIN targets."""
    ctes = {m.group(1).lower() for m in _CTE_RE.finditer(cleaned_stmt)}
    amap: dict[str, str] = {}
    for m in _FROM_JOIN_RE.finditer(cleaned_stmt):
        table, alias = m.group(1), m.group(2)
        if table.lower() in _RESERVED or table.lower() in ctes:
            continue
        if alias and alias.lower() not in _RESERVED:
            amap[alias.lower()] = table
        amap[table.split(".")[-1].lower()] = table
    return amap


def _on_clause(cleaned_stmt: str, on_end: int) -> str:
    m = _CLAUSE_END_RE.search(cleaned_stmt, on_end)
    return cleaned_stmt[on_end:m.start() if m else len(cleaned_stmt)]


def _group_by_cols(cleaned_stmt: str):
    """Yield (alias_or_None, column) for plain GROUP BY columns."""
    for m in _GROUP_BY_RE.finditer(cleaned_stmt):
        end = _GROUP_END_RE.search(cleaned_stmt, m.end())
        clause = cleaned_stmt[m.end(): end.start() if end else len(cleaned_stmt)]
        for piece in clause.split(","):
            qm = _PLAIN_COL_RE.fullmatch(piece.strip())
            if qm and qm.group(2).lower() not in _GROUP_SKIP:
                yield qm.group(1), qm.group(2)


def extract_probe_targets(sql: str, max_targets: int = MAX_TARGETS) -> list[ProbeTarget]:
    """Parse (table, column) probe targets out of the script.

    Only alias-qualified columns that resolve to a base table are kept —
    a column belonging to a subquery alias cannot be probed and is skipped.
    """
    targets: list[ProbeTarget] = []
    seen: set[tuple[str, str]] = set()

    def add(table: str, column: str, reason: str) -> None:
        key = (table.lower(), column.lower())
        if key in seen or len(targets) >= max_targets:
            return
        if not _IDENT_RE.match(table) or not re.fullmatch(r"[A-Za-z_]\w*", column):
            return
        seen.add(key)
        targets.append(ProbeTarget(table=table, column=column, reason=reason))

    for _, stmt in split_statements(sql):
        cleaned = clean_sql(stmt)
        amap = _alias_map(cleaned)

        for m in _ON_RE.finditer(cleaned):
            clause = _on_clause(cleaned, m.end())
            for eq in _EQ_QUALIFIED_RE.finditer(clause):
                for alias, col in ((eq.group(1), eq.group(2)), (eq.group(3), eq.group(4))):
                    table = amap.get(alias.lower())
                    if table:
                        add(table, col, "join_key")

        single_table = list(amap.values())[0] if len(set(amap.values())) == 1 and amap else ""
        for m in _CD_COL_RE.finditer(cleaned):
            alias, col = m.group(1), m.group(2)
            table = amap.get(alias.lower()) if alias else single_table
            if table:
                add(table, col, "count_distinct")

        for alias, col in _group_by_cols(cleaned):
            table = amap.get(alias.lower()) if alias else single_table
            if table:
                add(table, col, "group_key")

    return targets


# ---------------------------------------------------------------------------
# Probe execution
# ---------------------------------------------------------------------------

# Engines whose SQL supports table sampling for cheaper probes on big tables.
SAMPLE_DS = ("hive", "sparksql", "postgresql")


def effective_sample_pct(ds_type: str, sample_pct: int) -> int:
    """The sampling percentage actually applied (0 = full scan)."""
    return sample_pct if ds_type in SAMPLE_DS and 0 < sample_pct < 100 else 0


def _table_expr(table: str, ds_type: str, sample_pct: int) -> str:
    pct = effective_sample_pct(ds_type, sample_pct)
    if not pct:
        return table
    if ds_type == "postgresql":
        return f"{table} TABLESAMPLE SYSTEM ({pct})"
    return f"{table} TABLESAMPLE ({pct} PERCENT)"


def _top_sql(t: ProbeTarget, top_n: int, table_expr: str) -> str:
    return (
        f"SELECT {t.column} AS k, COUNT(*) AS cnt FROM {table_expr} "
        f"GROUP BY {t.column} ORDER BY cnt DESC LIMIT {top_n}"
    )


def _null_sql(t: ProbeTarget, table_expr: str) -> str:
    return (
        f"SELECT COUNT(*) AS total, "
        f"SUM(CASE WHEN {t.column} IS NULL THEN 1 ELSE 0 END) AS nulls "
        f"FROM {table_expr}"
    )


# Executors open a fresh connection per run(), so probing targets in
# parallel is safe; keep the fan-out modest to not hammer the engine.
MAX_PARALLEL_PROBES = 4


def _probe_one(executor, t: ProbeTarget, top_n: int, expr: str) -> ProbeResult:
    r = ProbeResult(target=t)
    try:
        nq = executor.run(_null_sql(t, expr), max_rows=1)
        r.total = int(nq.rows[0][0] or 0)
        r.null_count = int(nq.rows[0][1] or 0)
        r.elapsed_ms += nq.elapsed_ms
        tq = executor.run(_top_sql(t, top_n, expr), max_rows=top_n)
        r.top = [("NULL" if v is None else str(v), int(c)) for v, c in tq.rows]
        r.elapsed_ms += tq.elapsed_ms
    except Exception as exc:  # noqa: BLE001 — per-target failure stays local
        r.error = str(exc)
    return r


def run_probes(
    executor,
    targets: list[ProbeTarget],
    top_n: int = TOP_N,
    ds_type: str = "",
    sample_pct: int = 0,
) -> list[ProbeResult]:
    """Run the two bounded probe queries per target, targets in parallel."""
    targets = targets[:MAX_TARGETS]
    if not targets:
        return []

    def probe(t: ProbeTarget) -> ProbeResult:
        return _probe_one(executor, t, top_n, _table_expr(t.table, ds_type, sample_pct))

    if len(targets) == 1:
        return [probe(targets[0])]
    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_PROBES, len(targets))) as pool:
        return list(pool.map(probe, targets))  # map preserves target order


class ProbeCache:
    """Remembers the last probe run so 'verify' then 'analyze' (or repeated
    runs on the same SQL) reuse the measurements instead of re-querying.
    Not thread-safe on its own — callers guard it with their own lock."""

    def __init__(self) -> None:
        self._key: tuple | None = None
        self._results: list[ProbeResult] | None = None

    def get(self, key: tuple) -> list[ProbeResult] | None:
        return self._results if key == self._key else None

    def put(self, key: tuple, results: list[ProbeResult]) -> None:
        self._key, self._results = key, results

    def clear(self) -> None:
        self._key = self._results = None


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_VERDICT_KEYS = {
    "confirmed": "prb_verdict_confirmed",
    "suspect": "prb_verdict_suspect",
    "ok": "prb_verdict_ok",
    "empty": "prb_verdict_empty",
    "error": "prb_verdict_error",
}


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _safe_value(v: str, max_len: int = 20) -> str:
    """A key value safe for one markdown-table cell / prompt line."""
    v = re.sub(r"\s+", " ", v)
    if len(v) > max_len:
        v = v[: max_len - 1] + "…"
    return v.replace("|", "\\|").replace("`", "'")


def _top_preview(r: ProbeResult, n: int = 3) -> str:
    if not r.top or not r.total:
        return "-"
    return ", ".join(
        f"`{_safe_value(v)}` ({_pct(c / r.total)})" for v, c in r.top[:n]
    )


# SET blocks per analysis dialect; join-key skew and aggregation skew pick
# different switches.
_ENGINE_PARAMS: dict[str, dict[str, list[str]]] = {
    "spark": {
        "base": ["SET spark.sql.adaptive.enabled=true;"],
        "join": [
            "SET spark.sql.adaptive.skewJoin.enabled=true;",
            "SET spark.sql.adaptive.skewJoin.skewedPartitionFactor=5;",
            "SET spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes=256m;",
        ],
        "agg": ["SET spark.sql.shuffle.partitions=400;"],
    },
    "hive": {
        "base": [],
        "join": ["SET hive.optimize.skewjoin=true;", "SET hive.skewjoin.key=100000;"],
        "agg": ["SET hive.groupby.skewindata=true;"],
    },
    "maxcompute": {
        "base": [],
        "join": ["SET odps.sql.skewjoin=true;"],
        "agg": ["SET odps.sql.groupby.skewindata=true;"],
    },
}


def engine_params_for_results(results: list[ProbeResult], dialect: str, lang: str) -> str:
    """A paste-ready SET block for the measured skew, or '' when nothing confirmed."""
    confirmed = [r for r in results if r.verdict == "confirmed"]
    cfg = _ENGINE_PARAMS.get(dialect)
    if not confirmed or not cfg:
        return ""
    lines = list(cfg["base"])
    if any(r.target.reason == "join_key" for r in confirmed):
        lines += cfg["join"]
    if any(r.target.reason in ("count_distinct", "group_key") for r in confirmed):
        lines += cfg["agg"]
    head = dsk(normalize_lang(lang), "prb_engine_params")
    return head + "\n\n```sql\n" + "\n".join(lines) + "\n```"


def render_probe_section(
    results: list[ProbeResult],
    lang: str,
    dialect: str = "",
    sample_pct: int = 0,
) -> str:
    """Bilingual '## 倾斜验证（实测）' markdown section."""
    lang = normalize_lang(lang)
    if not results:
        return f"{dsk(lang, 'prb_section')}\n\n{dsk(lang, 'prb_no_targets')}\n"
    parts = [dsk(lang, "prb_section"), ""]
    confirmed = sum(1 for r in results if r.verdict == "confirmed")
    summary = (dsk(lang, "prb_summary_confirmed").format(n=confirmed)
               if confirmed else dsk(lang, "prb_summary_clean"))
    if sample_pct:
        summary += " " + dsk(lang, "prb_sampled_note").format(pct=sample_pct)
    parts.append(summary)
    parts.append("")
    parts.append(
        f"| {dsk(lang, 'prb_col_target')} | {dsk(lang, 'prb_col_reason')} | "
        f"{dsk(lang, 'prb_col_rows')} | {dsk(lang, 'prb_col_null')} | "
        f"{dsk(lang, 'prb_col_top')} | {dsk(lang, 'prb_col_verdict')} |"
    )
    parts.append("|---|---|---|---|---|---|")
    for r in results:
        t = r.target
        reason = dsk(lang, f"prb_reason_{t.reason}")
        verdict = dsk(lang, _VERDICT_KEYS[r.verdict])
        if r.error:
            err = r.error.replace("|", "\\|").replace("\n", " ")
            err = err if len(err) <= 80 else err[:79] + "…"
            parts.append(f"| `{t.table}.{t.column}` | {reason} | - | - | {err} | {verdict} |")
            continue
        parts.append(
            f"| `{t.table}.{t.column}` | {reason} | {r.total} | "
            f"{_pct(r.null_ratio)} | {_top_preview(r)} | {verdict} |"
        )
    if dialect:
        params = engine_params_for_results(results, dialect, lang)
        if params:
            parts += ["", params]
    parts.append("")
    return "\n".join(parts)


def _hot_values(r: ProbeResult) -> list[str]:
    """The concrete hot values worth isolating in a rewrite (NULL included)."""
    vals: list[str] = []
    null_listed = False
    for v, c in r.top:
        if not r.total or c / r.total < HOT_KEY_SUSPECT:
            break  # top is count-descending
        if v == "NULL":
            vals.append(f"NULL ({_pct(c / r.total)})")
            null_listed = True
        else:
            vals.append(f"'{_safe_value(v)}' ({_pct(c / r.total)})")
    if not null_listed and r.null_ratio >= NULL_CONFIRMED:
        vals.append(f"NULL ({_pct(r.null_ratio)})")
    return vals


def probe_lines_for_prompt(results: list[ProbeResult], lang: str) -> str:
    """Compact per-target measurement lines injected into the LLM prompt.

    Confirmed/suspect targets also list their concrete hot values so the
    rewrite can isolate them by value instead of guessing."""
    lang = normalize_lang(lang)
    lines = []
    for r in results:
        if r.error or not r.total:
            continue
        t = r.target
        top = ", ".join(f"{_safe_value(v)}={c}" for v, c in r.top[:3])
        line = (
            f"- {t.table}.{t.column} ({dsk(lang, f'prb_reason_{t.reason}')}): "
            f"rows={r.total}, null={_pct(r.null_ratio)}, "
            f"top1={_pct(r.top1_ratio)}, top: {top}"
        )
        hot = _hot_values(r)
        if hot:
            label = "热点值" if lang == "zh" else "hot values"
            line += f"\n  {label}: " + ", ".join(hot)
        lines.append(line)
    return "\n".join(lines)
