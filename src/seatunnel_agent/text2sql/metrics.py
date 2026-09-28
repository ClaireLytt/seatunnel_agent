"""Metric semantic layer — the "口径 whitelist" (PRD chat_bi section 3).

``schema_ddl.sql`` whitelists *tables*; ``metrics.yaml`` whitelists *metric
definitions*: which table, which aggregation expression, which dimensions a
business metric may be computed with. ``build_metric_sql`` expands a metric
into SQL **deterministically** (a pure function of its inputs, no LLM), so
the same question always produces byte-identical SQL — the core guarantee
of aggregation-caliber consistency.

Two metric kinds:
- ``additive``: a single aggregation over one table (SUM/COUNT/...).
- ``ratio``: numerator / denominator, each referencing an additive metric.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .matcher import tokenize
from .partition import TimeRange, pt_value
from .schema import SchemaStore, TableSchema

_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_IDENT_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")

# Identifiers immediately followed by "(" are function calls, not columns.
_FUNC_CALL_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")

# Non-function words that legitimately appear inside expressions/filters.
_EXPR_KEYWORDS = frozenset({
    "and", "or", "not", "in", "like", "between", "is", "null", "case",
    "when", "then", "else", "end", "distinct", "as", "true", "false",
    "int", "bigint", "double", "float", "string", "decimal", "date",
    "timestamp", "boolean", "interval", "day", "month", "year",
})


class MetricError(ValueError):
    """Raised by build_metric_sql for invalid parameters."""


#: Conventional metrics definition file, next to schema_ddl.sql.
DEFAULT_METRICS_PATH = Path("config") / "metrics.yaml"

_DATE_FORMATS = ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d")


def parse_date(raw: str):
    """Parse a user/LLM-supplied date string into a ``date``."""
    from datetime import datetime

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    raise MetricError(f"无法解析日期 '{raw}'（支持 YYYY-MM-DD / yyyyMMdd）")


def parse_time_range(start_raw: str, end_raw: str) -> TimeRange | None:
    """Build a TimeRange from optional start/end strings (None if both empty)."""
    start_raw, end_raw = (start_raw or "").strip(), (end_raw or "").strip()
    if not start_raw and not end_raw:
        return None
    start = parse_date(start_raw) if start_raw else None
    end = parse_date(end_raw) if end_raw else None
    return TimeRange(start=start or end, end=end or start)


@dataclass(frozen=True)
class MetricDef:
    name: str                     # unique id, snake_case English
    display_name: str = ""
    aliases: tuple[str, ...] = ()
    description: str = ""
    unit: str = ""
    owner: str = ""
    metric_type: str = "additive"  # "additive" | "ratio"
    # additive fields
    table: str = ""
    expression: str = ""
    time_column: str = ""
    dimensions: tuple[str, ...] = ()
    default_filters: tuple[str, ...] = ()
    # ratio fields (names of additive metrics)
    numerator: str = ""
    denominator: str = ""

    @property
    def is_ratio(self) -> bool:
        return self.metric_type == "ratio"

    def summary_line(self) -> str:
        """One line for the system prompt's metric catalog."""
        head = f"- {self.name} ({self.display_name})"
        if self.is_ratio:
            body = f"= {self.numerator} / {self.denominator}"
        else:
            body = f"= {self.expression} FROM {self.table}"
        desc = f" -- {self.description}" if self.description else ""
        return f"{head} {body}{desc}"


@dataclass
class MetricMatch:
    metric: MetricDef
    score: float
    hits: list[str] = field(default_factory=list)


_STRING_LITERAL_RE = re.compile(r"'(?:[^'\\]|\\.)*'")


def _expression_columns(expr: str) -> set[str]:
    """Column-like identifiers in an expression (function names and string
    literals excluded)."""
    expr = _STRING_LITERAL_RE.sub("''", expr)
    funcs = {m.group(1).lower() for m in _FUNC_CALL_RE.finditer(expr)}
    cols: set[str] = set()
    for m in _IDENT_RE.finditer(expr):
        word = m.group(0).lower()
        if word in funcs or word in _EXPR_KEYWORDS or word.isdigit():
            continue
        cols.add(word)
    return cols


def _parse_one(raw: dict, index: int, errors: list[str]) -> MetricDef | None:
    where = f"metrics[{index}]"
    name = str(raw.get("name", "")).strip()
    if not name:
        errors.append(f"{where}: 缺少 name")
        return None
    if not _NAME_RE.match(name):
        errors.append(f"{where}: name '{name}' 必须是小写蛇形英文标识符")
        return None
    where = f"metric '{name}'"

    mtype = str(raw.get("type", "additive")).strip().lower()
    if mtype not in ("additive", "ratio"):
        errors.append(f"{where}: type 只支持 additive / ratio (got '{mtype}')")
        return None

    aliases_raw = raw.get("aliases", [])
    if not isinstance(aliases_raw, list):
        errors.append(f"{where}: aliases 必须是列表")
        aliases_raw = []
    dims_raw = raw.get("dimensions", [])
    if not isinstance(dims_raw, list):
        errors.append(f"{where}: dimensions 必须是列表")
        dims_raw = []
    filters_raw = raw.get("default_filters", [])
    if not isinstance(filters_raw, list):
        errors.append(f"{where}: default_filters 必须是列表")
        filters_raw = []

    metric = MetricDef(
        name=name,
        display_name=str(raw.get("display_name", "") or name),
        aliases=tuple(str(a).strip() for a in aliases_raw if str(a).strip()),
        description=str(raw.get("description", "") or "").strip(),
        unit=str(raw.get("unit", "") or "").strip(),
        owner=str(raw.get("owner", "") or "").strip(),
        metric_type=mtype,
        table=str(raw.get("table", "") or "").strip(),
        expression=str(raw.get("expression", "") or "").strip(),
        time_column=str(raw.get("time_column", "") or "").strip(),
        dimensions=tuple(str(d).strip() for d in dims_raw if str(d).strip()),
        default_filters=tuple(str(f).strip() for f in filters_raw if str(f).strip()),
        numerator=str(raw.get("numerator", "") or "").strip(),
        denominator=str(raw.get("denominator", "") or "").strip(),
    )

    if mtype == "additive":
        if not metric.table:
            errors.append(f"{where}: additive 指标缺少 table")
        if not metric.expression:
            errors.append(f"{where}: additive 指标缺少 expression")
    else:
        if not metric.numerator or not metric.denominator:
            errors.append(f"{where}: ratio 指标必须给出 numerator 和 denominator")
    return metric


class MetricStore:
    """Registry of metric definitions, validated against the SchemaStore."""

    def __init__(self, metrics: list[MetricDef] | None = None) -> None:
        self._metrics: dict[str, MetricDef] = {}
        for m in metrics or []:
            self._metrics[m.name] = m

    def get(self, name: str) -> MetricDef | None:
        return self._metrics.get(name.strip().lower())

    @property
    def metrics(self) -> list[MetricDef]:
        return list(self._metrics.values())

    def __len__(self) -> int:
        return len(self._metrics)

    def catalog_summary(self) -> str:
        """One line per metric, for the system prompt."""
        return "\n".join(m.summary_line() for m in self._metrics.values())

    # ------------------------------------------------------------------
    # Loading & validation
    # ------------------------------------------------------------------

    @classmethod
    def from_text(
        cls, text: str, schema_store: SchemaStore | None = None,
    ) -> tuple["MetricStore", list[str]]:
        """Parse YAML text; returns (store, errors). Bad metrics are skipped."""
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover
            raise ValueError("加载指标定义需要 PyYAML: pip install pyyaml") from exc
        errors: list[str] = []
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            return cls(), [f"metrics.yaml 解析失败: {exc}"]
        if data is None:
            return cls(), []
        if not isinstance(data, dict) or not isinstance(data.get("metrics"), list):
            return cls(), ["metrics.yaml 顶层必须是含 metrics 列表的映射"]

        parsed: list[MetricDef] = []
        seen: set[str] = set()
        for i, raw in enumerate(data["metrics"]):
            if not isinstance(raw, dict):
                errors.append(f"metrics[{i}]: 必须是映射")
                continue
            before = len(errors)
            metric = _parse_one(raw, i, errors)
            if metric is None or len(errors) > before:
                continue
            if metric.name in seen:
                errors.append(f"metric '{metric.name}': 重复定义")
                continue
            seen.add(metric.name)
            parsed.append(metric)

        store = cls(parsed)
        if schema_store is not None:
            errors.extend(store.validate(schema_store))
            for msg in errors:
                # Drop metrics that failed schema validation so downstream
                # build_metric_sql can never see a half-valid definition.
                m = re.match(r"metric '(\w+)'", msg)
                if m:
                    store._metrics.pop(m.group(1), None)
        return store, errors

    @classmethod
    def from_file(
        cls, path: str | Path, schema_store: SchemaStore | None = None,
    ) -> tuple["MetricStore", list[str]]:
        p = Path(path)
        if not p.is_file():
            return cls(), [f"指标定义文件不存在: {p}"]
        return cls.from_text(p.read_text(encoding="utf-8"), schema_store)

    def validate(self, schema_store: SchemaStore) -> list[str]:
        """Cross-check every metric against the table whitelist."""
        errors: list[str] = []
        for m in self._metrics.values():
            if m.is_ratio:
                errors.extend(self._validate_ratio(m))
            else:
                errors.extend(self._validate_additive(m, schema_store))
        return errors

    def _validate_additive(
        self, m: MetricDef, schema_store: SchemaStore,
    ) -> list[str]:
        errors: list[str] = []
        where = f"metric '{m.name}'"
        table = schema_store.get(m.table)
        if table is None:
            return [f"{where}: 表 '{m.table}' 不在 schema 白名单中"]
        all_cols = {c.name.lower() for c in table.columns + table.partition_columns}

        for col in _expression_columns(m.expression):
            if col not in all_cols:
                errors.append(f"{where}: expression 引用了不存在的列 '{col}'")
        if m.time_column and m.time_column.lower() not in all_cols:
            errors.append(f"{where}: time_column '{m.time_column}' 不存在于表中")
        elif table.is_partitioned:
            # A metric on a partitioned table whose time_column is not the
            # partition column would always generate SQL without a partition
            # filter — rejected at execution time. Fail at load time instead.
            part_cols = {c.name.lower() for c in table.partition_columns}
            if not m.time_column or m.time_column.lower() not in part_cols:
                hint = table.partition_columns[0].name
                errors.append(
                    f"{where}: 表 '{m.table}' 是分区表，time_column 必须是"
                    f"分区列（如 '{hint}'），否则生成的 SQL 会因缺少分区过滤被拒绝"
                )
        for dim in m.dimensions:
            if dim.lower() not in all_cols:
                errors.append(f"{where}: dimension '{dim}' 不存在于表中")
        for f in m.default_filters:
            for col in _expression_columns(f):
                if col not in all_cols:
                    errors.append(
                        f"{where}: default_filter 引用了不存在的列 '{col}'"
                    )
        return errors

    def _validate_ratio(self, m: MetricDef) -> list[str]:
        errors: list[str] = []
        where = f"metric '{m.name}'"
        for role, ref in (("numerator", m.numerator), ("denominator", m.denominator)):
            target = self._metrics.get(ref)
            if target is None:
                errors.append(f"{where}: {role} '{ref}' 未定义")
            elif target.is_ratio:
                # v1 boundary: ratio may only reference additive metrics,
                # which also rules out reference cycles.
                errors.append(f"{where}: {role} '{ref}' 必须是 additive 指标")
        return errors

    # ------------------------------------------------------------------
    # Natural-language matching
    # ------------------------------------------------------------------

    def match(self, question: str, top_n: int = 5) -> list[MetricMatch]:
        """Rank metrics by relevance to the question (same tokenizer as tables)."""
        english, ngrams = tokenize(question)
        results: list[MetricMatch] = []
        for m in self._metrics.values():
            match = self._score(m, question, english, ngrams)
            if match.score > 0:
                results.append(match)
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_n]

    @staticmethod
    def _score(
        m: MetricDef, question: str, english: list[str], ngrams: list[str],
    ) -> MetricMatch:
        match = MetricMatch(metric=m, score=0.0)
        exact_names = [m.name.lower(), m.display_name.lower()]
        exact_names += [a.lower() for a in m.aliases]

        # Strongest signal: an alias/display name appearing verbatim in the
        # question (covers CJK aliases longer than the n-gram window).
        for alias in dict.fromkeys([m.display_name, *m.aliases]):
            if alias and alias.lower() in question.lower():
                match.score += 12.0
                match.hits.append(alias)

        for tok in english:
            if tok in exact_names:
                match.score += 10.0
                match.hits.append(tok)
            elif any(tok in name for name in exact_names if name):
                match.score += 4.0
                match.hits.append(tok)

        for gram in ngrams:
            weight = len(gram) / 2
            if any(gram in name for name in (m.display_name, *m.aliases)):
                match.score += 3.0 * weight
                match.hits.append(gram)
            elif gram in m.description:
                match.score += 1.0 * weight
                match.hits.append(gram)

        match.hits = list(dict.fromkeys(match.hits))[:8]
        return match


def load_metric_store(
    schema_store: SchemaStore | None = None,
    metrics_yaml: str | None = None,
    path: str | Path | None = None,
) -> tuple[MetricStore, list[str]]:
    """Load metrics from inline YAML, an explicit path, or the default file.

    Returns an empty store with no errors when nothing is configured — the
    semantic layer is strictly opt-in.
    """
    if metrics_yaml and metrics_yaml.strip():
        return MetricStore.from_text(metrics_yaml, schema_store)
    target = Path(path) if path else DEFAULT_METRICS_PATH
    if not target.is_file():
        if path:  # an explicit path that doesn't exist is an error
            return MetricStore(), [f"指标定义文件不存在: {target}"]
        return MetricStore(), []
    return MetricStore.from_file(target, schema_store)


# ----------------------------------------------------------------------
# Deterministic SQL expansion
# ----------------------------------------------------------------------


def _time_filter(
    metric: MetricDef,
    table: TableSchema,
    time_range: TimeRange | None,
    max_partition: str | None,
) -> str | None:
    """WHERE fragment for the metric's time column, or None.

    Partition columns use the conventional yyyyMMdd literal; ordinary date
    columns use ISO yyyy-MM-dd.
    """
    tcol = metric.time_column
    if not tcol:
        return None
    is_partition_col = tcol.lower() in {
        c.name.lower() for c in table.partition_columns
    }
    fmt = pt_value if is_partition_col else (lambda d: d.isoformat())

    if time_range is not None and not time_range.is_empty:
        start, end = time_range.start, time_range.end
        if start and end and start != end:
            return f"{tcol} >= '{fmt(start)}' AND {tcol} <= '{fmt(end)}'"
        d = start or end
        return f"{tcol} = '{fmt(d)}'"

    if max_partition and is_partition_col:
        return f"{tcol} = '{max_partition}'"

    if is_partition_col:
        raise MetricError(
            f"指标 '{metric.name}' 的时间列 '{tcol}' 是分区列，必须提供时间范围"
            "或 max_partition（可先调用 get_max_partition）"
        )
    return None


def _build_additive_sql(
    metric: MetricDef,
    table: TableSchema,
    dimensions: list[str],
    time_range: TimeRange | None,
    max_partition: str | None,
    extra_filters: list[str],
) -> str:
    conditions: list[str] = []
    tf = _time_filter(metric, table, time_range, max_partition)
    if tf:
        conditions.append(tf)
    conditions.extend(f"({f})" for f in metric.default_filters)
    conditions.extend(f"({f})" for f in extra_filters)

    select_items = list(dimensions) + [f"{metric.expression} AS {metric.name}"]
    lines = [
        "SELECT " + ", ".join(select_items),
        f"FROM {table.full_name}",
    ]
    if conditions:
        lines.append("WHERE " + "\n  AND ".join(conditions))
    if dimensions:
        lines.append("GROUP BY " + ", ".join(dimensions))
    return "\n".join(lines)


def _indent(sql: str, prefix: str = "  ") -> str:
    return "\n".join(prefix + line for line in sql.splitlines())


def build_metric_sql(
    metric: MetricDef,
    store: MetricStore,
    schema_store: SchemaStore,
    dimensions: list[str] | None = None,
    time_range: TimeRange | None = None,
    max_partition: str | None = None,
    extra_filters: list[str] | None = None,
) -> str:
    """Expand a metric into SQL. Pure function: identical inputs always
    produce byte-identical SQL. Raises :class:`MetricError` on invalid
    parameters (out-of-whitelist dimension, missing time range, ...).

    The caller MUST still pass the result through ``validate_sql`` before
    execution (double insurance; the agent's execute_sql tool already does).

    v1 limitations (documented in the PRD): a single ``max_partition`` value
    is applied to both sides of a ratio metric; ``extra_filters`` are applied
    to both sides too, so they should only reference columns present in both
    underlying tables.
    """
    dimensions = [d.strip() for d in (dimensions or []) if d.strip()]
    extra_filters = [f.strip() for f in (extra_filters or []) if f.strip()]

    if not metric.is_ratio:
        allowed = {d.lower() for d in metric.dimensions}
        for dim in dimensions:
            if dim.lower() not in allowed:
                raise MetricError(
                    f"维度 '{dim}' 不在指标 '{metric.name}' 的允许维度中"
                    f"（允许: {', '.join(metric.dimensions) or '无'}）"
                )
        table = schema_store.get(metric.table)
        if table is None:
            raise MetricError(f"表 '{metric.table}' 不在 schema 白名单中")
        return _build_additive_sql(
            metric, table, dimensions, time_range, max_partition, extra_filters,
        )

    num = store.get(metric.numerator)
    den = store.get(metric.denominator)
    if num is None or den is None or num.is_ratio or den.is_ratio:
        raise MetricError(
            f"ratio 指标 '{metric.name}' 的分子/分母定义无效"
        )
    allowed = {d.lower() for d in num.dimensions} & {
        d.lower() for d in den.dimensions
    }
    for dim in dimensions:
        if dim.lower() not in allowed:
            raise MetricError(
                f"维度 '{dim}' 必须同时在分子 '{num.name}' 和分母 "
                f"'{den.name}' 的允许维度中"
            )

    num_sql = build_metric_sql(
        num, store, schema_store, dimensions, time_range, max_partition,
        extra_filters,
    )
    den_sql = build_metric_sql(
        den, store, schema_store, dimensions, time_range, max_partition,
        extra_filters,
    )

    ratio_expr = (
        f"num.{num.name} * 1.0 / NULLIF(den.{den.name}, 0) AS {metric.name}"
    )
    if not dimensions:
        return "\n".join([
            f"SELECT {ratio_expr}",
            "FROM (",
            _indent(num_sql),
            ") num",
            "CROSS JOIN (",
            _indent(den_sql),
            ") den",
        ])

    dim_items = ", ".join(f"den.{d}" for d in dimensions)
    on_items = " AND ".join(f"den.{d} = num.{d}" for d in dimensions)
    return "\n".join([
        f"SELECT {dim_items}, {ratio_expr}",
        "FROM (",
        _indent(den_sql),
        ") den",
        "LEFT JOIN (",
        _indent(num_sql),
        ") num ON " + on_items,
    ])
