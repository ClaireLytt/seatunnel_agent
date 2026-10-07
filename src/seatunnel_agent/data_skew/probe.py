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
# into the outer scope.  DISTRIBUTE/SORT/CLUSTER BY terminate it too, or
# "GROUP BY dt DISTRIBUTE BY ..." would swallow the distribute columns.
_GROUP_END_RE = re.compile(
    r"\b(?:having|order|limit|union|window|qualify|distribute|sort|cluster)\b|[;)]",
    re.IGNORECASE)
# GROUPING SETS / ROLLUP / CUBE arguments and Spark's GROUP BY ALL are not
# plain columns.
_GROUP_SKIP = frozenset({"all", "grouping", "sets", "rollup", "cube"})
_PLAIN_COL_RE = re.compile(r"(?:([A-Za-z_]\w*)\.)?([A-Za-z_]\w*)")
# window PARTITION BY list (up to the frame's ORDER BY or closing paren)
_OVER_PARTITION_RE = re.compile(
    r"\bover\s*\(\s*partition\s+by\s+(.+?)(?:\border\s+by\b|\))",
    re.IGNORECASE | re.DOTALL)
# SELECT DISTINCT column list head (not COUNT(DISTINCT ...): SELECT-anchored)
_SELECT_DISTINCT_RE = re.compile(
    r"\bselect\s+distinct\s+(?!\s)((?:[^,()]|\([^()]*\))+)",
    re.IGNORECASE)


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

        # window PARTITION BY keys: a hot partition value funnels the whole
        # window into one task (DS009's measured counterpart)
        for m in _OVER_PARTITION_RE.finditer(cleaned):
            for col_m in _PLAIN_COL_RE.finditer(m.group(1)):
                alias, col = col_m.group(1), col_m.group(2)
                if col.lower() in _GROUP_SKIP:
                    continue
                table = amap.get(alias.lower()) if alias else single_table
                if table:
                    add(table, col, "window_key")

        # SELECT DISTINCT: the leading column concentrates the dedup shuffle
        for m in _SELECT_DISTINCT_RE.finditer(cleaned):
            head = m.group(1)
            col_m = _PLAIN_COL_RE.match(head.strip())
            if not col_m:
                continue
            # a function call is not a plain column
            rest = head.strip()[col_m.end():].lstrip()
            if rest.startswith("("):
                continue
            alias, col = col_m.group(1), col_m.group(2)
            table = amap.get(alias.lower()) if alias else single_table
            if table:
                add(table, col, "distinct_key")

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


def _measured_hot_values(r: ProbeResult) -> list[str]:
    """Raw hot values (no NULL) above the suspect threshold, count-descending.

    Values are returned untouched: display escaping/truncation happens at
    the rendering site, and SQL hints must carry the exact measured value
    or they would target a key that does not exist."""
    vals: list[str] = []
    for v, c in r.top:
        if not r.total or c / r.total < HOT_KEY_SUSPECT:
            break
        if v != "NULL":
            vals.append(v)
    return vals


_NUM_LITERAL_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def _hint_literal(v: str) -> str:
    """A hot value as a SKEWJOIN-hint literal: numbers bare, strings quoted."""
    if _NUM_LITERAL_RE.match(v):
        return v
    v = (v.replace("\\", "\\\\").replace('"', '\\"')
          .replace("\n", "\\n").replace("\r", "\\r"))
    return f'"{v}"'


def engine_params_for_results(results: list[ProbeResult], dialect: str, lang: str) -> str:
    """A paste-ready SET block for the measured skew, or '' when nothing confirmed."""
    lang = normalize_lang(lang)
    confirmed = [r for r in results if r.verdict == "confirmed"]
    cfg = _ENGINE_PARAMS.get(dialect)
    if not confirmed or not cfg:
        return ""
    lines = list(cfg["base"])
    if any(r.target.reason == "join_key" for r in confirmed):
        lines += cfg["join"]
    if any(r.target.reason in ("count_distinct", "group_key") for r in confirmed):
        lines += cfg["agg"]
    # Fill the measured hot values into concrete, per-key hints instead of
    # leaving only the generic switches.
    hot_label = "实测热点值" if lang == "zh" else "measured hot values"
    for r in confirmed:
        hot = _measured_hot_values(r)
        if not hot:
            continue
        t = r.target
        lines.append(f"-- {t.table}.{t.column} {hot_label}: "
                     + ", ".join(f"'{_safe_value(v)}'" for v in hot[:5]))
        if dialect == "maxcompute" and r.target.reason == "join_key":
            vals = "".join(f"({_hint_literal(v)})" for v in hot[:5])
            lines.append(f"/*+ SKEWJOIN({t.table}({t.column})({vals})) */")
    head = dsk(lang, "prb_engine_params")
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
        templates = render_rewrite_templates(results, lang)
        if templates:
            parts += ["", templates]
        advice = render_storage_advice(results, lang)
        if advice:
            parts += ["", advice]
    parts.append("")
    return "\n".join(parts)


def render_storage_advice(results: list[ProbeResult], lang: str) -> str:
    """Storage/modeling-layer advice for the confirmed-skew columns.

    Rewrites fix one script; a hot key that is also a partition / bucket /
    sync-split key skews every downstream job, so confirmed columns get a
    per-column note: don't use it as a distribution key, prefer a
    high-cardinality uniform key, and roll up the hot dimension instead."""
    lang = normalize_lang(lang)
    zh = lang == "zh"
    lines: list[str] = []
    for r in results:
        if r.verdict != "confirmed" or len(lines) >= 4:
            continue
        t = r.target
        if r.top1_ratio >= HOT_KEY_CONFIRMED:
            hot_v = _safe_value(r.top[0][0]) if r.top else "?"
            lines.append(
                f"- `{t.table}.{t.column}` top1≈{_pct(r.top1_ratio)}（热值 `'{hot_v}'`）："
                "不宜作为分区键 / 分桶键 / 同步分片键（partition_column）——"
                "建议改用高基数均匀键（ID 类）；下游频繁按该维度 GROUP BY/JOIN 时，"
                "考虑预聚合上卷，不再直接扫明细热 key"
                if zh else
                f"- `{t.table}.{t.column}` top1≈{_pct(r.top1_ratio)} (hot value `'{hot_v}'`): "
                "unsuitable as a partition / bucket / sync-split key (partition_column) — "
                "prefer a high-cardinality uniform key (ID-like); if downstream jobs "
                "GROUP BY/JOIN this dimension often, pre-aggregate a rollup instead of "
                "rescanning the hot detail keys"
            )
        elif r.null_ratio >= NULL_CONFIRMED:
            lines.append(
                f"- `{t.table}.{t.column}` NULL 占比 {_pct(r.null_ratio)}："
                "作分区/分片键会把 NULL 行集中到同一分区——上游先补默认值，"
                "或该列不作分布键"
                if zh else
                f"- `{t.table}.{t.column}` NULL ratio {_pct(r.null_ratio)}: "
                "as a partition/split key all NULL rows funnel into one partition — "
                "backfill a default upstream, or keep this column out of distribution keys"
            )
    if not lines:
        return ""
    return dsk(lang, "prb_storage_head") + "\n\n" + "\n".join(lines)


def _salt_n(r: ProbeResult) -> int:
    """Salting factor from the measured top1 share (~top1% / 2, clamped)."""
    return min(64, max(8, int(r.top1_ratio * 50)))


def render_rewrite_templates(results: list[ProbeResult], lang: str) -> str:
    """Deterministic rewrite skeletons for the confirmed targets, with the
    measured hot values filled in — usable without any LLM. At most three
    templates; the column list stays a placeholder for the user."""
    lang = normalize_lang(lang)
    zh = lang == "zh"
    blocks: list[str] = []
    for r in results:
        if r.verdict != "confirmed" or len(blocks) >= 3:
            continue
        t = r.target
        hot = _measured_hot_values(r)
        if t.reason == "join_key" and hot:
            vals = ", ".join(_hint_literal(v) for v in hot[:5])
            c = (f"-- 热点键隔离：{t.table}.{t.column} 实测热点 {vals}" if zh else
                 f"-- hot-key isolation: measured hot {t.table}.{t.column} values {vals}")
            sel = "SELECT /* 列清单 */ *" if zh else "SELECT /* column list */ *"
            blocks.append(
                f"```sql\n{c}\n"
                f"{sel} FROM {t.table} a JOIN dim b ON a.{t.column} = b.{t.column}\n"
                f"WHERE a.{t.column} IN ({vals})      "
                + ("-- 热点分支：小表侧可 MAPJOIN/BROADCAST" if zh
                   else "-- hot branch: MAPJOIN/BROADCAST the small side") + "\n"
                f"UNION ALL\n"
                f"{sel} FROM {t.table} a JOIN dim b ON a.{t.column} = b.{t.column}\n"
                f"WHERE a.{t.column} NOT IN ({vals});\n```")
        elif t.reason == "join_key" and r.null_ratio >= NULL_CONFIRMED:
            c = (f"-- NULL 键拆分：{t.table}.{t.column} 实测 NULL 占比 {_pct(r.null_ratio)}"
                 if zh else
                 f"-- NULL-key split: measured {t.table}.{t.column} NULL ratio {_pct(r.null_ratio)}")
            sel = "SELECT /* 列清单 */ *" if zh else "SELECT /* column list */ *"
            blocks.append(
                f"```sql\n{c}\n"
                f"{sel} FROM {t.table} a JOIN dim b ON a.{t.column} = b.{t.column}\n"
                f"WHERE a.{t.column} IS NOT NULL\n"
                f"UNION ALL\n"
                f"{sel} FROM {t.table} a WHERE a.{t.column} IS NULL;  "
                + ("-- NULL 行不参与关联，维表列补 NULL" if zh
                   else "-- NULL rows skip the join; pad dim columns with NULL") + "\n```")
        elif t.reason == "count_distinct":
            c = (f"-- 两阶段去重计数：{t.table}.{t.column}" if zh
                 else f"-- two-stage distinct count: {t.table}.{t.column}")
            blocks.append(
                f"```sql\n{c}\n"
                f"SELECT COUNT(1) AS distinct_cnt\n"
                f"FROM (SELECT {t.column} FROM {t.table} GROUP BY {t.column}) dedup;\n```")
        elif t.reason in ("group_key", "distinct_key") and hot:
            n = _salt_n(r)
            c = (f"-- 两阶段加盐聚合：{t.table}.{t.column} 实测 top1≈{_pct(r.top1_ratio)}，盐值 N={n}"
                 if zh else
                 f"-- two-stage salted aggregation: measured {t.table}.{t.column} "
                 f"top1≈{_pct(r.top1_ratio)}, salt N={n}")
            blocks.append(
                f"```sql\n{c}\n"
                f"SELECT {t.column}, SUM(pv) AS pv\n"
                f"FROM (\n"
                f"  SELECT {t.column}, CAST(rand() * {n} AS INT) AS salt, COUNT(*) AS pv\n"
                f"  FROM {t.table}\n"
                f"  GROUP BY {t.column}, CAST(rand() * {n} AS INT)\n"
                f") pre\n"
                f"GROUP BY {t.column};\n```")
        elif t.reason == "window_key" and hot:
            vals = ", ".join(_hint_literal(v) for v in hot[:3])
            line = (f"`{t.table}.{t.column}` 热点分区值 {vals}：在 PARTITION BY 中追加细分列，"
                    "或先按热点值拆分计算再合并" if zh else
                    f"`{t.table}.{t.column}` hot partition values {vals}: add a finer "
                    "column to PARTITION BY, or split the hot values out and union back")
            blocks.append(f"- {line}")
    if not blocks:
        return ""
    return dsk(lang, "prb_rewrite_head") + "\n\n" + "\n\n".join(blocks)


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
