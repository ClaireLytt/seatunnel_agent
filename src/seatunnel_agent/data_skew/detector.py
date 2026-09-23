"""Deterministic static data-skew rules for SQL scripts.

Regex/scanner based (no external SQL parser): each rule is best-effort and
biased toward high-precision skew patterns that are visible at the syntax
level. Value-dependent skew (actual hot keys, table sizes) needs runtime
statistics and is left to the LLM layer — see prompts.py.

All rules operate on a length-preserving cleaned copy of the SQL (string
literals and comments blanked with spaces) so match offsets map back to
original line numbers.
"""

from __future__ import annotations

import re

from .i18n import normalize_lang
from .report import Severity, SkewFinding

DIALECTS = ("spark", "maxcompute", "hive")

_DIALECT_ALIASES = {
    "sparksql": "spark",
    "spark3": "spark",
    "odps": "maxcompute",
    "mc": "maxcompute",
    "hivesql": "hive",
}

MAX_JOINS_THRESHOLD = 5


def normalize_dialect(dialect: str) -> str:
    d = (dialect or "spark").strip().lower().replace(" ", "")
    d = _DIALECT_ALIASES.get(d, d)
    return d if d in DIALECTS else "spark"


# ---------------------------------------------------------------------------
# SQL text utilities
# ---------------------------------------------------------------------------

def clean_sql(sql: str) -> str:
    """Blank out string literals and comments, preserving length/newlines."""
    out = list(sql)
    i, n = 0, len(sql)

    def blank(start: int, end: int) -> None:
        for j in range(start, min(end, n)):
            if out[j] != "\n":
                out[j] = " "

    while i < n:
        ch = sql[i]
        if ch in ("'", '"'):
            quote = ch
            start = i
            i += 1
            while i < n:
                if sql[i] == "\\":
                    i += 2
                    continue
                if sql[i] == quote:
                    i += 1
                    break
                i += 1
            blank(start + 1, i - 1 if i <= n and i > start + 1 else i)
        elif ch == "-" and i + 1 < n and sql[i + 1] == "-":
            start = i
            while i < n and sql[i] != "\n":
                i += 1
            blank(start, i)
        elif ch == "/" and i + 1 < n and sql[i + 1] == "*":
            start = i
            i += 2
            while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i = min(i + 2, n)
            # keep optimizer hints /*+ ... */ visible
            if not sql[start:start + 3] == "/*+":
                blank(start, i)
        else:
            i += 1
    return "".join(out)


def split_statements(sql: str) -> list[tuple[int, str]]:
    """Split a script on top-level ';'. Returns [(offset, statement_text)]."""
    cleaned = clean_sql(sql)
    stmts: list[tuple[int, str]] = []
    start = 0
    for m in re.finditer(";", cleaned):
        seg = sql[start:m.start()]
        if seg.strip():
            stmts.append((start, seg))
        start = m.end()
    tail = sql[start:]
    if tail.strip():
        stmts.append((start, tail))
    return stmts or [(0, sql)]


def line_of(sql: str, offset: int) -> int:
    return sql.count("\n", 0, max(0, offset)) + 1


# ---------------------------------------------------------------------------
# Rule text catalog (zh is the source language; en mirrors it)
# ---------------------------------------------------------------------------

RULE_TEXTS: dict[str, dict[str, dict[str, str]]] = {
    "DS001": {  # count(distinct)
        "zh": {
            "desc": "COUNT(DISTINCT {col}) 会把全部数据汇聚到单个 Reducer/Task 去重计数",
            "impact": "数据量大时该 Task 成为长尾，任务整体被拖慢甚至 OOM",
            "suggestion": "{sugg}",
            "benefit": "去重下推为两阶段聚合，消除单点热点",
        },
        "en": {
            "desc": "COUNT(DISTINCT {col}) funnels all rows into a single reducer/task for dedup counting",
            "impact": "On large data that task becomes a long tail, slowing or OOM-ing the whole job",
            "suggestion": "{sugg}",
            "benefit": "Dedup becomes a two-stage aggregation, removing the single hot task",
        },
    },
    "DS002": {  # multiple count(distinct)
        "zh": {
            "desc": "同一 SELECT 中出现 {n} 个 COUNT(DISTINCT)，引擎会展开为多次全量 shuffle 或退化为单点聚合",
            "impact": "shuffle 量成倍放大，倾斜叠加",
            "suggestion": "拆分为多个子查询分别去重后再 JOIN，或改用 GROUPING SETS / 两阶段 GROUP BY",
            "benefit": "每个指标独立并行计算，避免多重去重叠加倾斜",
        },
        "en": {
            "desc": "{n} COUNT(DISTINCT) in one SELECT — the engine expands them into multiple full shuffles or a single-point aggregation",
            "impact": "Shuffle volume multiplies and skew compounds",
            "suggestion": "Split into separate dedup subqueries joined back, or use GROUPING SETS / two-stage GROUP BY",
            "benefit": "Each metric computes independently in parallel, avoiding compounded dedup skew",
        },
    },
    "DS003": {  # global distinct
        "zh": {
            "desc": "SELECT DISTINCT 触发全字段全量 shuffle 去重",
            "impact": "所有数据按整行 hash 重分布，字段多时代价高",
            "suggestion": "确认是否真的需要去重；需要时可改为 GROUP BY 明确去重键，或先过滤/裁剪列再去重",
            "benefit": "缩小参与去重的数据量与列数",
        },
        "en": {
            "desc": "SELECT DISTINCT triggers a full shuffle dedup over all columns",
            "impact": "Every row is redistributed by whole-row hash; expensive with many columns",
            "suggestion": "Confirm dedup is really needed; if so use GROUP BY on explicit keys, or filter/prune columns first",
            "benefit": "Less data and fewer columns take part in the dedup",
        },
    },
    "DS004": {  # union dedup
        "zh": {
            "desc": "UNION（不带 ALL）会对两侧结果做隐式全量去重",
            "impact": "额外一次全量 shuffle + 排序去重；数据不重复时纯属浪费",
            "suggestion": "如两侧数据本身不重复或允许重复，改为 UNION ALL",
            "benefit": "省去一次全量 shuffle 去重",
        },
        "en": {
            "desc": "UNION (without ALL) implicitly deduplicates both sides",
            "impact": "An extra full shuffle + sort dedup; pure waste when rows never overlap",
            "suggestion": "If the two sides don't overlap (or duplicates are fine), use UNION ALL",
            "benefit": "Removes one full shuffle-dedup pass",
        },
    },
    "DS005": {  # global order by
        "zh": {
            "desc": "末尾的全局 ORDER BY 不带 LIMIT，会把全部结果送入单个 Task 排序",
            "impact": "单 Task 全量排序，是最典型的人为单点",
            "suggestion": "{sugg}",
            "benefit": "排序并行化或只排 TopN，消除单点",
        },
        "en": {
            "desc": "Trailing global ORDER BY without LIMIT pushes the entire result into one task to sort",
            "impact": "Single-task full sort — the classic self-inflicted single point",
            "suggestion": "{sugg}",
            "benefit": "Sort becomes parallel (or TopN only), removing the single point",
        },
    },
    "DS006": {  # cartesian
        "zh": {
            "desc": "JOIN 缺少 ON 条件或为 CROSS JOIN，产生笛卡尔积",
            "impact": "输出行数 = 两表行数乘积，数据爆炸并全部倾斜到少数 Task",
            "suggestion": "补全等值关联条件；确需笛卡尔积时限制小表行数并显式写 CROSS JOIN",
            "benefit": "避免数据爆炸",
        },
        "en": {
            "desc": "JOIN without ON (or CROSS JOIN) produces a cartesian product",
            "impact": "Output rows = product of both tables — data explodes and lands on few tasks",
            "suggestion": "Add the equi-join condition; if a cartesian is intended, cap the small side and write CROSS JOIN explicitly",
            "benefit": "Avoids data explosion",
        },
    },
    "DS007": {  # null key join
        "zh": {
            "desc": "{jt} JOIN 的关联键 {key} 未做 NULL 过滤/打散，NULL 值会全部落到同一个 Task",
            "impact": "关联键 NULL 占比高时形成超大热点分区",
            "suggestion": "主表 NULL 键先过滤（WHERE {key} IS NOT NULL 后 UNION ALL 回来），或打散：ON coalesce({key}, concat('rn_', rand())) = ...",
            "benefit": "NULL 热点被过滤或随机打散到多个 Task",
        },
        "en": {
            "desc": "{jt} JOIN key {key} has no NULL filter/scatter — all NULL keys hash to the same task",
            "impact": "A NULL-heavy key creates one oversized hot partition",
            "suggestion": "Filter NULL keys first (WHERE {key} IS NOT NULL, UNION ALL them back), or scatter: ON coalesce({key}, concat('rn_', rand())) = ...",
            "benefit": "NULL hotspot filtered out or randomly spread over many tasks",
        },
    },
    "DS008": {  # expr on join key
        "zh": {
            "desc": "JOIN 关联条件中对键使用了函数/类型转换：{expr}",
            "impact": "隐式转换或函数计算可能让大量不同值折叠成同一个 hash 值，制造倾斜，且无法利用分桶/索引",
            "suggestion": "在上游把关联键清洗成一致的类型与格式，JOIN 时用裸列关联",
            "benefit": "关联键分布还原，shuffle 均匀",
        },
        "en": {
            "desc": "Join condition applies a function/cast to the key: {expr}",
            "impact": "Implicit casts/functions can collapse many distinct values into one hash bucket, causing skew and defeating bucketing/indexes",
            "suggestion": "Normalize key type/format upstream and join on bare columns",
            "benefit": "Key distribution restored, shuffle stays even",
        },
    },
    "DS009": {  # window no partition
        "zh": {
            "desc": "窗口函数 OVER 子句缺少 PARTITION BY，全部数据进入同一个窗口分区",
            "impact": "整表在单 Task 内排序/计算，等价于全局单点",
            "suggestion": "为 OVER() 增加合理的 PARTITION BY 维度；确需全局编号时先聚合缩小数据量",
            "benefit": "窗口计算按分区并行",
        },
        "en": {
            "desc": "Window OVER clause has no PARTITION BY — all rows fall into one window partition",
            "impact": "Whole table sorts/computes inside a single task, i.e. a global single point",
            "suggestion": "Add a sensible PARTITION BY to OVER(); if a global row number is required, shrink the data first",
            "benefit": "Window computation parallelizes per partition",
        },
    },
    "DS010": {  # dynamic partition insert
        "zh": {
            "desc": "动态分区写入未加 DISTRIBUTE BY，分区间数据量差异会直接映射为 Task 倾斜与小文件",
            "impact": "热点分区拖慢写入，且产生大量小文件",
            "suggestion": "追加 DISTRIBUTE BY {col}（热点分区可再叠加 rand() 打散），MaxCompute 亦可开启 odps.sql.reshuffle",
            "benefit": "写入负载均匀、抑制小文件",
        },
        "en": {
            "desc": "Dynamic partition insert without DISTRIBUTE BY — uneven partition sizes map directly to task skew and small files",
            "impact": "Hot partitions slow the write and spawn many small files",
            "suggestion": "Append DISTRIBUTE BY {col} (optionally + rand() for hot partitions)",
            "benefit": "Even write load, fewer small files",
        },
    },
    "DS011": {  # too many joins
        "zh": {
            "desc": "单条语句包含 {n} 个 JOIN（阈值 {limit}）",
            "impact": "执行计划复杂，任一环节倾斜都难以定位",
            "suggestion": "拆分为中间表/CTE 分步落地，缩小每步 shuffle 规模，便于定位倾斜环节",
            "benefit": "倾斜环节可独立定位与调优",
        },
        "en": {
            "desc": "Single statement contains {n} joins (threshold {limit})",
            "impact": "Complex plan; skew in any stage is hard to isolate",
            "suggestion": "Materialize intermediate tables/CTEs step by step to shrink each shuffle and localize skew",
            "benefit": "Skewed stage becomes independently tunable",
        },
    },
    "DS012": {  # rand in join
        "zh": {
            "desc": "JOIN 条件中出现非确定函数 {fn}，每次求值结果不同",
            "impact": "关联结果不可复现，且可能导致重算阶段数据错配",
            "suggestion": "打散热点时应把 rand() 物化到子查询列后再关联，不要写在 ON 条件里直接比较",
            "benefit": "结果可复现，打散逻辑正确",
        },
        "en": {
            "desc": "Non-deterministic function {fn} inside a JOIN condition — it re-evaluates per row/stage",
            "impact": "Join results are non-reproducible and retries may mismatch rows",
            "suggestion": "For salting, materialize rand() as a column in a subquery first, then join on it — never call it inside ON",
            "benefit": "Reproducible results, correct salting",
        },
    },
    "DS013": {  # broadcast hint suggestion
        "zh": {
            "desc": "语句包含多表 JOIN 且未使用广播提示；若其中一侧是小表（维表/聚合结果），可广播避免 shuffle",
            "impact": "大表参与 shuffle join 时，热点 key 直接形成倾斜",
            "suggestion": "{sugg}",
            "benefit": "小表广播后大表不再 shuffle，倾斜 key 失效",
        },
        "en": {
            "desc": "Multi-table JOIN without a broadcast hint; if one side is small (dim table / aggregate), broadcast it to skip the shuffle",
            "impact": "Shuffle join on a big table turns hot keys straight into skew",
            "suggestion": "{sugg}",
            "benefit": "With the small side broadcast, the big table stops shuffling and hot keys stop mattering",
        },
    },
}

# Dialect-specific suggestion snippets ------------------------------------

_CD_SUGG = {
    "spark": (
        "改为两阶段：先 GROUP BY {col} 去重再 COUNT，或用 approx_count_distinct({col})"
        "（允许约 2% 误差时）"
    ),
    "maxcompute": "改为两阶段：内层 GROUP BY {col} 去重，外层 COUNT(1)；避免直接 COUNT(DISTINCT)",
    "hive": "改为两阶段：内层 GROUP BY {col} 去重，外层 COUNT(1)；或 set hive.groupby.skewindata=true",
}
_CD_SUGG_EN = {
    "spark": (
        "Rewrite as two stages: GROUP BY {col} then COUNT, or use approx_count_distinct({col}) "
        "when ~2% error is acceptable"
    ),
    "maxcompute": "Rewrite as two stages: inner GROUP BY {col} dedup, outer COUNT(1); avoid raw COUNT(DISTINCT)",
    "hive": "Rewrite as two stages: inner GROUP BY {col}, outer COUNT(1); or set hive.groupby.skewindata=true",
}

_OB_SUGG = {
    "spark": "加 LIMIT 只取 TopN；或去掉 ORDER BY 交给下游 BI 排序；必须全排时可先 SORT BY 局部有序",
    "maxcompute": "加 LIMIT 只取 TopN，或改 DISTRIBUTE BY + SORT BY 局部有序",
    "hive": "加 LIMIT 只取 TopN，或改 DISTRIBUTE BY + SORT BY 局部有序",
}
_OB_SUGG_EN = {
    "spark": "Add LIMIT for TopN, drop ORDER BY and sort downstream, or use SORT BY for per-partition order",
    "maxcompute": "Add LIMIT for TopN, or switch to DISTRIBUTE BY + SORT BY for per-partition order",
    "hive": "Add LIMIT for TopN, or switch to DISTRIBUTE BY + SORT BY for per-partition order",
}

_BC_SUGG = {
    "spark": "小表侧加 /*+ BROADCAST(t) */ 提示（或确认 spark.sql.autoBroadcastJoinThreshold 生效）",
    "maxcompute": "小表侧加 /*+ MAPJOIN(t) */ 提示",
    "hive": "小表侧加 /*+ MAPJOIN(t) */ 提示，或 set hive.auto.convert.join=true",
}
_BC_SUGG_EN = {
    "spark": "Add /*+ BROADCAST(t) */ on the small side (or verify spark.sql.autoBroadcastJoinThreshold)",
    "maxcompute": "Add /*+ MAPJOIN(t) */ on the small side",
    "hive": "Add /*+ MAPJOIN(t) */ on the small side, or set hive.auto.convert.join=true",
}

# Engine-level hints emitted once per report when join/groupby skew fired.
ENGINE_HINTS = {
    "spark": {
        "zh": [
            "开启 AQE 倾斜自动处理：`set spark.sql.adaptive.enabled=true; set spark.sql.adaptive.skewJoin.enabled=true;`",
            "GROUP BY 倾斜可提高并行度：`set spark.sql.shuffle.partitions=<按数据量调大>` 或对热点 key 加盐两阶段聚合",
        ],
        "en": [
            "Enable AQE skew handling: `set spark.sql.adaptive.enabled=true; set spark.sql.adaptive.skewJoin.enabled=true;`",
            "For GROUP BY skew raise parallelism: `set spark.sql.shuffle.partitions=<larger>` or salt hot keys with two-stage aggregation",
        ],
    },
    "maxcompute": {
        "zh": [
            "JOIN 倾斜可用 `/*+ SKEWJOIN(t) */`（可带热点值：`/*+ SKEWJOIN(t(c1)((v1)(v2))) */`）",
            "GROUP BY 倾斜可开启：`set odps.sql.groupby.skewindata=true;`",
        ],
        "en": [
            "For join skew use `/*+ SKEWJOIN(t) */` (optionally with hot values: `/*+ SKEWJOIN(t(c1)((v1)(v2))) */`)",
            "For GROUP BY skew: `set odps.sql.groupby.skewindata=true;`",
        ],
    },
    "hive": {
        "zh": [
            "JOIN 倾斜：`set hive.optimize.skewjoin=true; set hive.skewjoin.key=100000;`",
            "GROUP BY 倾斜：`set hive.groupby.skewindata=true;`",
        ],
        "en": [
            "Join skew: `set hive.optimize.skewjoin=true; set hive.skewjoin.key=100000;`",
            "GROUP BY skew: `set hive.groupby.skewindata=true;`",
        ],
    },
}


def _texts(rule_key: str, lang: str, **args) -> dict[str, str]:
    t = RULE_TEXTS[rule_key][lang]
    return {k: v.format(**args) if args else v for k, v in t.items()}


def _finding(
    rule_key: str,
    severity: Severity,
    category: str,
    lang: str,
    line: int,
    before: str = "",
    after: str = "",
    **args,
) -> SkewFinding:
    t = _texts(rule_key, lang, **args)
    return SkewFinding(
        severity=severity,
        category=category,
        location="",
        line=line,
        key=rule_key,
        args=dict(args),
        description=t["desc"],
        impact=t["impact"],
        suggestion=t["suggestion"],
        before=before,
        after=after,
        benefit=t["benefit"],
        source="static",
    )


def _snippet(sql: str, start: int, end: int, limit: int = 60) -> str:
    s = " ".join(sql[start:end].split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


# ---------------------------------------------------------------------------
# Individual rules — each takes (sql, cleaned, dialect, lang) and yields findings
# ---------------------------------------------------------------------------

_CD_RE = re.compile(r"\bcount\s*\(\s*distinct\b\s*([^)]*)\)", re.IGNORECASE)


def _rule_count_distinct(sql: str, cleaned: str, dialect: str, lang: str) -> list[SkewFinding]:
    out: list[SkewFinding] = []
    matches = list(_CD_RE.finditer(cleaned))
    sugg_map = _CD_SUGG if lang == "zh" else _CD_SUGG_EN
    for m in matches:
        col = " ".join((m.group(1) or "col").split()) or "col"
        before = _snippet(sql, m.start(), m.end())
        if dialect == "spark":
            after = f"approx_count_distinct({col}) / 两阶段 GROUP BY" if lang == "zh" else f"approx_count_distinct({col}) / two-stage GROUP BY"
        else:
            after = (
                f"SELECT COUNT(1) FROM (SELECT {col} FROM … GROUP BY {col}) t"
            )
        out.append(
            _finding(
                "DS001", Severity.MEDIUM, "count_distinct", lang,
                line_of(sql, m.start()), before=before, after=after,
                col=col, sugg=sugg_map[dialect].format(col=col),
            )
        )
    # multiple count(distinct) inside one statement
    if len(matches) >= 2:
        out.append(
            _finding(
                "DS002", Severity.HIGH, "multi_count_distinct", lang,
                line_of(sql, matches[0].start()),
                before=f"{len(matches)} × COUNT(DISTINCT …)",
                after="GROUPING SETS / 分列子查询 JOIN" if lang == "zh" else "GROUPING SETS / split subqueries + JOIN",
                n=len(matches),
            )
        )
    return out


_DISTINCT_RE = re.compile(r"\bselect\s+distinct\b", re.IGNORECASE)


def _rule_global_distinct(sql: str, cleaned: str, dialect: str, lang: str) -> list[SkewFinding]:
    out = []
    for m in _DISTINCT_RE.finditer(cleaned):
        out.append(
            _finding(
                "DS003", Severity.LOW, "global_distinct", lang,
                line_of(sql, m.start()),
                before="SELECT DISTINCT …",
                after="GROUP BY <去重键>" if lang == "zh" else "GROUP BY <dedup keys>",
            )
        )
    return out


_UNION_RE = re.compile(r"\bunion\b(?!\s+all\b)", re.IGNORECASE)


def _rule_union(sql: str, cleaned: str, dialect: str, lang: str) -> list[SkewFinding]:
    out = []
    for m in _UNION_RE.finditer(cleaned):
        out.append(
            _finding(
                "DS004", Severity.MEDIUM, "union_dedup", lang,
                line_of(sql, m.start()),
                before="… UNION …",
                after="… UNION ALL …",
            )
        )
    return out


_ORDER_RE = re.compile(r"\border\s+by\b", re.IGNORECASE)
_LIMIT_RE = re.compile(r"\blimit\s+\d", re.IGNORECASE)


def _rule_global_orderby(sql: str, cleaned: str, dialect: str, lang: str) -> list[SkewFinding]:
    # Flag the LAST order by of the statement when no LIMIT follows it and it
    # is not inside an OVER(...) window.
    out = []
    matches = [m for m in _ORDER_RE.finditer(cleaned) if not _inside_over(cleaned, m.start())]
    if not matches:
        return out
    last = matches[-1]
    tail = cleaned[last.end():]
    if not _LIMIT_RE.search(tail):
        sugg_map = _OB_SUGG if lang == "zh" else _OB_SUGG_EN
        out.append(
            _finding(
                "DS005", Severity.HIGH, "global_orderby", lang,
                line_of(sql, last.start()),
                before="ORDER BY … (无 LIMIT)" if lang == "zh" else "ORDER BY … (no LIMIT)",
                after="ORDER BY … LIMIT N / DISTRIBUTE BY + SORT BY",
                sugg=sugg_map[dialect],
            )
        )
    return out


def _inside_over(cleaned: str, pos: int) -> bool:
    """True when position sits inside an OVER ( ... ) window spec."""
    open_idx = cleaned.rfind("(", 0, pos)
    while open_idx != -1:
        # matching close paren after pos?
        depth = 0
        for j in range(open_idx, len(cleaned)):
            if cleaned[j] == "(":
                depth += 1
            elif cleaned[j] == ")":
                depth -= 1
                if depth == 0:
                    if j > pos:
                        prefix = cleaned[max(0, open_idx - 12):open_idx]
                        if re.search(r"\bover\s*$", prefix, re.IGNORECASE):
                            return True
                    break
        open_idx = cleaned.rfind("(", 0, open_idx)
    return False


_JOIN_RE = re.compile(
    r"\b(?:(left|right|full|inner|cross)\s+(?:outer\s+)?)?join\s+([\w.`\"]+)",
    re.IGNORECASE,
)
_CLAUSE_AFTER_JOIN_RE = re.compile(
    r"\b(on|using|join|where|group\s+by|order\s+by|having|union|limit|window|select)\b",
    re.IGNORECASE,
)


def _rule_joins(sql: str, cleaned: str, dialect: str, lang: str) -> list[SkewFinding]:
    out: list[SkewFinding] = []
    joins = list(_JOIN_RE.finditer(cleaned))
    if not joins:
        return out

    has_hint = bool(re.search(r"/\*\+\s*(broadcast|mapjoin|broadcastjoin)\b", cleaned, re.IGNORECASE))

    for m in joins:
        jt = (m.group(1) or "inner").lower()
        # look ahead: does an ON/USING arrive before the next clause?
        nxt = _CLAUSE_AFTER_JOIN_RE.search(cleaned, m.end())
        kw = nxt.group(1).lower().replace(" ", "") if nxt else ""
        if jt == "cross":
            out.append(
                _finding(
                    "DS006", Severity.HIGH, "join_cartesian", lang,
                    line_of(sql, m.start()),
                    before=_snippet(sql, m.start(), m.end()),
                    after="JOIN … ON a.key = b.key",
                )
            )
            continue
        if kw not in ("on", "using"):
            # comma-separated FROM lists aren't matched here; only bare JOIN
            out.append(
                _finding(
                    "DS006", Severity.HIGH, "join_cartesian", lang,
                    line_of(sql, m.start()),
                    before=_snippet(sql, m.start(), m.end()),
                    after="JOIN … ON a.key = b.key",
                )
            )

    # too many joins in one statement
    if len(joins) > MAX_JOINS_THRESHOLD:
        out.append(
            _finding(
                "DS011", Severity.LOW, "too_many_joins", lang,
                line_of(sql, joins[0].start()),
                n=len(joins), limit=MAX_JOINS_THRESHOLD,
            )
        )

    # broadcast hint suggestion (once per statement, batch engines only)
    if len(joins) >= 1 and not has_hint:
        sugg_map = _BC_SUGG if lang == "zh" else _BC_SUGG_EN
        hint = "/*+ BROADCAST(dim) */" if dialect == "spark" else "/*+ MAPJOIN(dim) */"
        out.append(
            _finding(
                "DS013", Severity.LOW, "join_hint", lang,
                line_of(sql, joins[0].start()),
                before="SELECT … FROM big JOIN dim ON …",
                after=f"SELECT {hint} … FROM big JOIN dim ON …",
                sugg=sugg_map[dialect],
            )
        )
    return out


_ON_CLAUSE_RE = re.compile(r"\bon\b(.{1,400}?)(?=\b(?:left|right|full|inner|cross|join|where|group\s+by|order\s+by|having|union|limit|select)\b|;|$)", re.IGNORECASE | re.DOTALL)
_ON_FUNC_RE = re.compile(r"\b(cast|coalesce|nvl|substr|substring|concat|trim|upper|lower|to_date|date_format|from_unixtime|unix_timestamp|regexp_replace|split|if)\s*\(", re.IGNORECASE)
_ON_RAND_RE = re.compile(r"\b(rand|random|uuid|current_timestamp|now)\s*\(", re.IGNORECASE)


def _rule_on_clause(sql: str, cleaned: str, dialect: str, lang: str) -> list[SkewFinding]:
    out: list[SkewFinding] = []
    for m in _ON_CLAUSE_RE.finditer(cleaned):
        clause = m.group(1)
        base = m.start(1)
        rnd = _ON_RAND_RE.search(clause)
        if rnd:
            out.append(
                _finding(
                    "DS012", Severity.HIGH, "rand_in_join", lang,
                    line_of(sql, base + rnd.start()),
                    before=_snippet(sql, base + rnd.start(), base + rnd.start() + 40),
                    after="子查询先物化盐值列，再 ON t.salt_key = …" if lang == "zh" else "materialize salt column in a subquery, then join on it",
                    fn=rnd.group(1) + "()",
                )
            )
        fn = _ON_FUNC_RE.search(clause)
        if fn and not rnd:
            expr_snip = _snippet(sql, base + fn.start(), min(base + fn.start() + 50, m.end(1)))
            out.append(
                _finding(
                    "DS008", Severity.MEDIUM, "join_key_expr", lang,
                    line_of(sql, base + fn.start()),
                    before=expr_snip,
                    after="ON a.key = b.key（上游统一类型/格式）" if lang == "zh" else "ON a.key = b.key (normalize upstream)",
                    expr=expr_snip,
                )
            )
    return out


_OUTER_JOIN_RE = re.compile(r"\b(left|right|full)\s+(?:outer\s+)?join\b", re.IGNORECASE)
_NULL_GUARD_RE = re.compile(r"\b(coalesce|nvl)\s*\(|is\s+not\s+null", re.IGNORECASE)


def _rule_null_key(sql: str, cleaned: str, dialect: str, lang: str) -> list[SkewFinding]:
    """Outer joins whose ON keys have no NULL guard anywhere in the statement."""
    out: list[SkewFinding] = []
    for m in _OUTER_JOIN_RE.finditer(cleaned):
        jt = m.group(1).upper()
        on_m = _ON_CLAUSE_RE.search(cleaned, m.end())
        if not on_m:
            continue
        clause = on_m.group(1)
        # extract first bare column reference used as key (either side of '=')
        key_m = re.search(r"([\w]+\.[\w]+|\w+)\s*=", clause) or re.search(r"=\s*([\w]+\.[\w]+|\w+)", clause)
        key = key_m.group(1) if key_m else "join_key"
        if _NULL_GUARD_RE.search(clause):
            continue
        # a WHERE ... key IS NOT NULL later in the statement also counts
        rest = cleaned[on_m.end(): on_m.end() + 600]
        if re.search(re.escape(key.split(".")[-1]) + r"\s+is\s+not\s+null", rest, re.IGNORECASE):
            continue
        out.append(
            _finding(
                "DS007", Severity.MEDIUM, "join_null_key", lang,
                line_of(sql, m.start()),
                before=f"{jt} JOIN … ON {key} = …",
                after=f"ON coalesce({key}, concat('rn_', rand())) = …",
                jt=jt, key=key,
            )
        )
    return out


_OVER_RE = re.compile(r"\bover\s*\(([^)]*)\)", re.IGNORECASE | re.DOTALL)


def _rule_window(sql: str, cleaned: str, dialect: str, lang: str) -> list[SkewFinding]:
    out = []
    for m in _OVER_RE.finditer(cleaned):
        inner = m.group(1)
        if not re.search(r"\bpartition\s+by\b", inner, re.IGNORECASE):
            out.append(
                _finding(
                    "DS009", Severity.HIGH, "window_no_partition", lang,
                    line_of(sql, m.start()),
                    before=_snippet(sql, m.start(), m.end()),
                    after="OVER (PARTITION BY <维度> ORDER BY …)" if lang == "zh" else "OVER (PARTITION BY <dim> ORDER BY …)",
                )
            )
    return out


_DYN_PART_RE = re.compile(
    r"\binsert\s+(?:overwrite|into)\s+(?:table\s+)?[\w.]+\s+partition\s*\(\s*([\w]+)\s*\)",
    re.IGNORECASE,
)
_DISTRIBUTE_RE = re.compile(r"\bdistribute\s+by\b", re.IGNORECASE)


def _rule_dynamic_partition(sql: str, cleaned: str, dialect: str, lang: str) -> list[SkewFinding]:
    out = []
    for m in _DYN_PART_RE.finditer(cleaned):
        col = m.group(1)
        if _DISTRIBUTE_RE.search(cleaned, m.end()):
            continue
        out.append(
            _finding(
                "DS010", Severity.MEDIUM, "dynamic_partition", lang,
                line_of(sql, m.start()),
                before=f"INSERT … PARTITION ({col}) SELECT …",
                after=f"… SELECT … DISTRIBUTE BY {col}",
                col=col,
            )
        )
    return out


_RULES = (
    _rule_count_distinct,
    _rule_global_distinct,
    _rule_union,
    _rule_global_orderby,
    _rule_joins,
    _rule_on_clause,
    _rule_null_key,
    _rule_window,
    _rule_dynamic_partition,
)

# Categories that justify emitting engine-level hints.
_HINT_TRIGGERS = {
    "count_distinct", "multi_count_distinct", "join_null_key",
    "join_key_expr", "join_hint", "join_cartesian",
}


def detect_skew(
    sql: str, dialect: str = "spark", lang: str = "zh"
) -> tuple[list[SkewFinding], list[str]]:
    """Run all static rules per statement. Returns (findings, engine_hints)."""
    dialect = normalize_dialect(dialect)
    lang = normalize_lang(lang)
    findings: list[SkewFinding] = []
    for offset, stmt in split_statements(sql):
        cleaned = clean_sql(stmt)
        # skip pure DDL / SET statements
        if not re.search(r"\b(select|insert)\b", cleaned, re.IGNORECASE):
            continue
        prefix_lines = sql.count("\n", 0, offset)
        for rule in _RULES:
            for f in rule(stmt, cleaned, dialect, lang):
                f.line += prefix_lines
                findings.append(f)
    findings.sort(key=lambda f: (f.line, f.key))

    hints: list[str] = []
    if any(f.category in _HINT_TRIGGERS for f in findings):
        hints = list(ENGINE_HINTS[dialect][lang])
    return findings, hints
