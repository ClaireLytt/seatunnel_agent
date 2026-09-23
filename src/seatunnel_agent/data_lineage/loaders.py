"""Builders that populate a LineageGraph from the two supported sources.

1. ``from_sql_files`` / ``from_sql_dir`` — parse local SQL scripts with the
   existing regex lineage tracers (table + column level).
2. ``from_hive_meta`` — ad-hoc query of the Hive metadata lineage table
   (``zz.dwm_meta_table_lineage_df`` by default, latest ``pt`` partition;
   ``relation_*`` columns describe DOWNSTREAM tables only).
"""

from __future__ import annotations

import re
from pathlib import Path

from ..sql_review.lineage import extract_table_lineage
from ..sql_review.linter import split_statements
from ..sql_review.runner import collect_sql_files
from ..text2sql.executor.base import (
    DatabaseExecutor,
    config_from_env,
    create_executor,
)
from ..text2sql.lineage import trace_lineage
from ..text2sql.schema import SchemaStore
from .config import load_lineage_config
from .graph import ColumnEdge, LineageGraph

_META_TABLE_RE = re.compile(r"^\w+(?:\.\w+)?$")
_PARTITION_RE = re.compile(r"^[\w\-]+$")

_HIVE_MAX_ROWS = 200_000

_META_COLUMNS = (
    "source_type_name", "database_name", "table_name", "table_layer",
    "relation_source_type_name", "relation_database_name",
    "relation_table_name", "relation_layer",
    "is_relation_sla_type", "relation_sla_time",
    "relation_base_line_name_list",
)


def meta_table_from_env() -> str:
    return load_lineage_config().meta_table


def _validated_meta_table(meta_table: str | None) -> str:
    meta_table = (meta_table or meta_table_from_env()).strip()
    if not _META_TABLE_RE.match(meta_table):
        raise ValueError(f"非法的血缘元数据表名: {meta_table!r}")
    return meta_table


# ----------------------------------------------------------------------
# SQL file source
# ----------------------------------------------------------------------

def from_sql_files(
    paths: list[Path] | list[str],
    store: SchemaStore | None = None,
    cache_base: str | Path = "logs",
    dialect: str = "hive",
) -> tuple[LineageGraph, list[str]]:
    """Parse each SQL file and merge table- and column-level lineage.

    Never raises on a bad file — it is skipped with a warning instead.
    Per-file fragments are cached under ``logs/.lineage_cache/files/`` keyed
    by (path, mtime, size), so unchanged files skip re-parsing entirely.
    """
    from .cache import load_file_fragment, save_file_fragment

    graph = LineageGraph()
    warnings: list[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        # 文件级缓存仅在无 SchemaStore 时启用：store 会影响解析结果，
        # 缓存键无法感知 schema 变化。
        if store is None:
            cached = load_file_fragment(path, base=cache_base, dialect=dialect)
            if cached is not None:
                graph.merge(cached)
                continue
        try:
            # 读内容前先 stat：缓存键必须对应读到的内容，读后再 stat 会把
            # 期间被修改的文件的新 (mtime, size) 记到旧内容上，缓存永远不失效
            pre_stat = path.stat()
            sql_text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            warnings.append(f"无法读取 {path}: {exc}")
            continue
        fragment = LineageGraph()
        parsed_ok = True
        try:
            _load_sql_script(fragment, sql_text, origin=f"sql:{path.name}",
                             store=store, dialect=dialect)
        except Exception as exc:  # noqa: BLE001 — one bad file must not kill the build
            warnings.append(f"解析 {path} 失败: {exc}")
            parsed_ok = False
        graph.merge(fragment)
        if parsed_ok and store is None:
            save_file_fragment(fragment, path, base=cache_base, stat=pre_stat,
                               dialect=dialect)
    return graph, warnings


def from_sql_dir(
    directory: str | Path,
    store: SchemaStore | None = None,
    cache_base: str | Path = "logs",
    dialect: str = "hive",
) -> tuple[LineageGraph, list[str]]:
    files = collect_sql_files(directory)
    if not files:
        return LineageGraph(), [f"目录 {directory} 下没有找到 *.sql 文件"]
    return from_sql_files(files, store=store, cache_base=cache_base, dialect=dialect)


def _load_sql_script(
    graph: LineageGraph,
    sql_text: str,
    origin: str,
    store: SchemaStore | None = None,
    dialect: str = "hive",
) -> None:
    for _offset, statement in split_statements(sql_text):
        lineage = extract_table_lineage(statement, store=store)
        if not lineage.sources and not lineage.targets:
            continue
        for name in lineage.sources + lineage.targets:
            graph.add_node(name, origins={origin})
        for target in lineage.targets:
            for source in lineage.sources:
                graph.add_edge(source, target, source="sql", confidence="high")
        if lineage.targets:
            _load_column_edges(
                graph, statement, lineage.targets[0], lineage.sources, store,
                dialect=dialect,
            )


def _load_column_edges(
    graph: LineageGraph,
    statement: str,
    target: str,
    sources: list[str],
    store: SchemaStore | None,
    dialect: str = "hive",
) -> None:
    from .sqlglot_lineage import extract_column_edges

    # AST-based lineage when sqlglot is installed (extras: lineage);
    # None or empty means fall through to the regex tracer below.
    ast_edges = extract_column_edges(statement, target, sources, dialect=dialect)
    if ast_edges:
        for edge in ast_edges:
            edge.source = "sql"
            edge.confidence = "high"
            graph.add_column_edge(edge)
        return
    try:
        traced = trace_lineage(statement, store=store)
    except Exception:  # noqa: BLE001 — column lineage is best-effort
        return
    # Unqualified columns are attributable when there is exactly one source.
    sole_source = sources[0] if len(sources) == 1 else ""
    for col in traced.output_columns:
        src_table = col.source_table or sole_source
        if not src_table or not col.source_column:
            continue
        if col.output_name in ("", "*"):
            continue
        graph.add_column_edge(ColumnEdge(
            src_table=src_table,
            src_column=col.source_column,
            dst_table=target,
            dst_column=col.output_name,
            expression=col.expression,
            is_aggregation=col.is_aggregation,
            source="sql",
            confidence="low",  # 正则降级解析，可信度低于 sqlglot AST
        ))


# ----------------------------------------------------------------------
# Hive metadata source
# ----------------------------------------------------------------------

def _parse_bool(value: object) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in ("1", "true", "yes", "y", "是")


def _parse_list(value: object) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text or text.lower() in ("null", "none", "[]"):
        return []
    text = text.strip("[]")
    parts = [p.strip().strip("'\"") for p in text.split(",")]
    return [p for p in parts if p]


def resolve_partition(executor: DatabaseExecutor, meta_table: str) -> str:
    """Latest ``pt`` partition: SHOW PARTITIONS cache first, then max(pt)."""
    partition = executor.get_max_partition(meta_table)
    if partition:
        return partition
    result = executor.run(f"SELECT max(pt) FROM {meta_table}", max_rows=1)
    if result.rows and result.rows[0] and result.rows[0][0]:
        return str(result.rows[0][0])
    raise RuntimeError(f"无法确定 {meta_table} 的最新分区（SHOW PARTITIONS 与 max(pt) 均为空）")


def from_hive_meta(
    executor: DatabaseExecutor,
    meta_table: str | None = None,
    partition: str | None = None,
    max_rows: int = _HIVE_MAX_ROWS,
) -> LineageGraph:
    meta_table = _validated_meta_table(meta_table)
    if partition is None or not str(partition).strip():
        partition = resolve_partition(executor, meta_table)
    partition = str(partition).strip()
    if not _PARTITION_RE.match(partition):
        raise ValueError(f"非法的分区值: {partition!r}")

    sql = (
        f"SELECT {', '.join(_META_COLUMNS)} "
        f"FROM {meta_table} WHERE pt = '{partition}'"
    )
    result = executor.run(sql, max_rows=max_rows)

    graph = LineageGraph()
    index = {name: i for i, name in enumerate(result.columns)}

    def cell(row: tuple, column: str) -> object:
        i = index.get(column)
        if i is None or i >= len(row):
            return None
        return row[i]

    for row in result.rows:
        database = str(cell(row, "database_name") or "").strip()
        table = str(cell(row, "table_name") or "").strip()
        if not table:
            continue
        up_name = f"{database}.{table}" if database else table
        graph.add_node(
            up_name,
            source_type=str(cell(row, "source_type_name") or "").strip(),
            layer=str(cell(row, "table_layer") or "").strip(),
            origins={"hive_meta"},
        )

        rel_db = str(cell(row, "relation_database_name") or "").strip()
        rel_table = str(cell(row, "relation_table_name") or "").strip()
        if not rel_table:
            continue  # leaf row: node only, no downstream edge
        down_name = f"{rel_db}.{rel_table}" if rel_db else rel_table
        graph.add_node(
            down_name,
            source_type=str(cell(row, "relation_source_type_name") or "").strip(),
            layer=str(cell(row, "relation_layer") or "").strip(),
            is_sla=_parse_bool(cell(row, "is_relation_sla_type")),
            sla_time=str(cell(row, "relation_sla_time") or "").strip(),
            baselines=_parse_list(cell(row, "relation_base_line_name_list")),
            origins={"hive_meta"},
        )
        # relation_* columns record DOWNSTREAM lineage only.
        graph.add_edge(up_name, down_name, source="hive_meta", confidence="high")
    return graph


def hive_executor_from_env() -> DatabaseExecutor | None:
    config = config_from_env("hive")
    if config is None:
        return None
    return create_executor(config)


# ----------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------

def _hive_graph_cached(
    meta_table: str | None,
    partition: str | None,
    use_cache: bool,
) -> tuple[LineageGraph, str, bool]:
    """Hive graph with local TTL cache → (graph, partition, from_cache)."""
    from .cache import load_cached_graph, save_cached_graph

    meta_table = _validated_meta_table(meta_table)
    pt = str(partition).strip() if partition and str(partition).strip() else None

    if use_cache and pt:
        cached = load_cached_graph(meta_table, pt)
        if cached is not None:
            return cached, pt, True

    executor = hive_executor_from_env()
    if executor is None:
        raise RuntimeError("未配置 HIVE_HOST（.env），无法从 Hive 元数据加载血缘")
    if pt is None:
        pt = str(resolve_partition(executor, meta_table)).strip()
        if use_cache:
            cached = load_cached_graph(meta_table, pt)
            if cached is not None:
                return cached, pt, True

    graph = from_hive_meta(executor, meta_table=meta_table, partition=pt)
    if use_cache:
        save_cached_graph(graph, meta_table, pt)
    return graph, pt, False


def build_graph(
    sql_dir: str | Path | None = None,
    sql_files: list[str] | list[Path] | None = None,
    use_hive: bool = False,
    meta_table: str | None = None,
    partition: str | None = None,
    seatunnel_dir: str | Path | None = None,
    store: SchemaStore | None = None,
    use_cache: bool = True,
    sql_dialect: str = "hive",
) -> tuple[LineageGraph, list[str]]:
    """Build and merge the graph from every requested source.

    Hive failures never raise when another source is also present (offline
    mode) — the error is surfaced as a warning instead. The Hive graph is
    served from the local TTL cache when fresh (see ``cache.py``).
    ``sql_dialect`` picks the sqlglot dialect used to parse SQL files.
    """
    from .seatunnel_loader import from_seatunnel_dir

    graph = LineageGraph()
    warnings: list[str] = []
    has_sql_source = bool(sql_dir or sql_files or seatunnel_dir)

    if sql_dir:
        sub, warns = from_sql_dir(sql_dir, store=store, dialect=sql_dialect)
        graph.merge(sub)
        warnings.extend(warns)
    if sql_files:
        sub, warns = from_sql_files(sql_files, store=store, dialect=sql_dialect)
        graph.merge(sub)
        warnings.extend(warns)
    if seatunnel_dir:
        sub, warns = from_seatunnel_dir(seatunnel_dir)
        graph.merge(sub)
        warnings.extend(warns)

    if use_hive:
        try:
            sub, pt, from_cache = _hive_graph_cached(meta_table, partition, use_cache)
            graph.merge(sub)
            if from_cache:
                warnings.append(
                    f"Hive 血缘图来自本地缓存（pt={pt}），如需强制刷新请用 --no-cache"
                )
        except Exception as exc:  # noqa: BLE001 — degrade to SQL-only when possible
            if has_sql_source:
                warnings.append(f"Hive 元数据加载失败，已降级为仅 SQL 血缘: {exc}")
            else:
                raise

    return graph, warnings
