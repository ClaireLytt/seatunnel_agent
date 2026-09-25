# -*- coding: utf-8 -*-
"""Lineage from SeaTunnel job configs (HOCON): source tables → sink tables.

A lightweight quote-aware brace scanner extracts the ``source``/``sink``
sections and their connector blocks — no HOCON dependency. Table names come
from the common connector keys (``table_name``/``table-name``/``table``/
``table_path``/``topic``, qualified with ``database``/``database-name`` when
unqualified); a source-side ``query``/``sql`` falls back to the SQL lineage
parser.

``transform`` sections additionally yield best-effort column lineage:
FieldMapper mappings become high-confidence column edges, and a Sql
transform's query is parsed with sqlglot (medium confidence). Logical table
names are resolved through ``result_table_name``/``source_table_name``;
topologies that cannot be resolved keep table-level edges only.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..sql_review.lineage import extract_table_lineage
from .graph import ColumnEdge, LineageGraph
from .sqlglot_lineage import extract_column_edges

_SECTION_RE = re.compile(r'"?([A-Za-z0-9_\-.]+)"?\s*\{')

# 前缀允许行首/逗号/左花括号，同一行的多对 k=v（HOCON 合法写法）都能匹配到；
# 数组分支须排在无引号分支前，否则 `[` 会被当作无引号 token 的开头。
_KV_RE = re.compile(
    r'(?:^|(?<=[\s,{]))\s*"?([A-Za-z0-9_\-.]+)"?\s*[=:]\s*'
    r'(?:"""(.*?)"""|"([^"\n]*)"|\'([^\'\n]*)\'|(\[[^\]]*\])|([^\s#]+))',
    re.S,
)

_TABLE_KEYS = {"table_name", "table", "table_path", "tables", "topic"}
_DATABASE_KEYS = {"database_name", "database"}
_QUERY_KEYS = {"query", "sql"}

_CONFIG_SUFFIXES = (".conf", ".config", ".json")


def collect_seatunnel_files(directory: str | Path) -> list[Path]:
    root = Path(directory)
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in _CONFIG_SUFFIXES
    )


def _is_escaped(text: str, i: int) -> bool:
    """True when text[i] is preceded by an odd number of backslashes."""
    backslashes = 0
    j = i - 1
    while j >= 0 and text[j] == "\\":
        backslashes += 1
        j -= 1
    return backslashes % 2 == 1


def _strip_comments(text: str) -> str:
    """Remove ``#`` / ``//`` comments outside of quoted strings."""
    out: list[str] = []
    quote: str | None = None
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if quote:
            out.append(ch)
            if ch == quote and not _is_escaped(text, i):
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "#" or text[i:i + 2] == "//":
            while i < n and text[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _match_brace(text: str, open_idx: int) -> int:
    """Index of the ``}`` matching ``text[open_idx] == '{'``, or -1."""
    depth = 0
    quote: str | None = None
    for i in range(open_idx, len(text)):
        ch = text[i]
        if quote:
            if ch == quote and not _is_escaped(text, i):
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _blocks(text: str) -> list[tuple[str, str]]:
    """Immediate child blocks ``name { body }`` of the given text."""
    blocks: list[tuple[str, str]] = []
    pos = 0
    while True:
        m = _SECTION_RE.search(text, pos)
        if m is None:
            break
        open_idx = m.end() - 1
        end = _match_brace(text, open_idx)
        if end < 0:
            break
        blocks.append((m.group(1), text[m.end():end]))
        pos = end + 1
    return blocks


def _kv_pairs(body: str, raw_keys: bool = False) -> list[tuple[str, str]]:
    """``raw_keys=True`` keeps keys verbatim (FieldMapper keys are column names)."""
    pairs: list[tuple[str, str]] = []
    for m in _KV_RE.finditer(body):
        value = next((g for g in m.groups()[1:] if g is not None), "")
        value = value.strip().rstrip(",;").strip()
        key = m.group(1) if raw_keys else m.group(1).lower().replace("-", "_")
        pairs.append((key, value))
    return pairs


def _qualify(table: str, database: str) -> str:
    table = table.strip().strip("`")
    if not table:
        return ""
    if "." in table or not database:
        return table
    return f"{database}.{table}"


def _plugin_tables(pairs: list[tuple[str, str]], allow_query: bool) -> list[str]:
    database = next(
        (v for k, v in pairs if k in _DATABASE_KEYS and v), ""
    ).strip().strip("`")
    tables: list[str] = []
    for key, value in pairs:
        if key in _TABLE_KEYS and value:
            if value.startswith("[") and value.endswith("]"):
                value = value[1:-1]
            for part in re.split(r"[,;]", value):
                name = _qualify(part.strip().strip("\"'"), database)
                if name:
                    tables.append(name)
    if not tables and allow_query:
        for key, value in pairs:
            if key in _QUERY_KEYS and value:
                tables.extend(extract_table_lineage(value).sources)
    seen: set[str] = set()
    unique = []
    for name in tables:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return unique


def _load_config(graph: LineageGraph, text: str, origin: str) -> None:
    text = _strip_comments(text)
    sources: list[tuple[str, str]] = []  # (table, plugin)
    sinks: list[tuple[str, str]] = []
    source_infos: list[dict[str, str]] = []  # {table, result_name}
    sink_infos: list[dict[str, str]] = []    # {table, source_name}
    transforms: list[dict[str, str]] = []    # {plugin, body, source_name, result_name}
    for section, body in _blocks(text):
        role = section.lower()
        if role == "transform":
            for plugin, plugin_body in _blocks(body):
                pairs_list = _kv_pairs(plugin_body)
                pairs = dict(pairs_list)
                transforms.append({
                    "plugin": plugin,
                    "body": plugin_body,
                    "source_name": pairs.get("source_table_name", ""),
                    "result_name": pairs.get("result_table_name", ""),
                    "query": next(
                        (v for k, v in pairs_list if k in _QUERY_KEYS and v), ""
                    ),
                })
            continue
        if role not in ("source", "sink"):
            continue
        for plugin, plugin_body in _blocks(body):
            pairs_list = _kv_pairs(plugin_body)
            pairs = dict(pairs_list)
            for table in _plugin_tables(pairs_list, allow_query=(role == "source")):
                if role == "source":
                    sources.append((table, plugin))
                    source_infos.append({
                        "table": table,
                        "result_name": pairs.get("result_table_name", ""),
                    })
                else:
                    sinks.append((table, plugin))
                    sink_infos.append({
                        "table": table,
                        "source_name": pairs.get("source_table_name", ""),
                    })
    for table, plugin in sources + sinks:
        graph.add_node(table, source_type=plugin, origins={origin})
    # source×sink 笛卡尔积是启发式（未看 transform 的真实映射），标 medium
    for src, _ in sources:
        for dst, _ in sinks:
            graph.add_edge(src, dst, source="seatunnel", confidence="medium")
    _load_transform_columns(graph, transforms, source_infos, sink_infos)


def _load_transform_columns(
    graph: LineageGraph,
    transforms: list[dict[str, str]],
    sources: list[dict[str, str]],
    sinks: list[dict[str, str]],
) -> None:
    """Best-effort column edges from transform blocks; unresolvable
    topologies silently keep table-level lineage only."""
    if not transforms:
        return
    logical: dict[str, str] = {}
    ambiguous: set[str] = set()
    for s in sources:
        key = s["result_name"].lower()
        if not key:
            continue
        if key in logical and logical[key] != s["table"]:
            ambiguous.add(key)
        else:
            logical[key] = s["table"]
    # 一个逻辑名对应多张物理表时无法归属列级血缘，保守跳过（表级不受影响）
    for key in ambiguous:
        del logical[key]
    transform_inputs = {t["source_name"].lower() for t in transforms if t["source_name"]}
    for tr in transforms:
        # 链式 transform（输入来自另一个 transform，或输出喂给下一个）不做列级推断
        if tr["source_name"] and tr["source_name"].lower() not in logical:
            continue
        if tr["result_name"] and tr["result_name"].lower() in transform_inputs:
            continue
        src = logical.get(tr["source_name"].lower(), "") if tr["source_name"] else ""
        if not src and len(sources) == 1:
            src = sources[0]["table"]
        dst = ""
        if tr["result_name"]:
            dst = next(
                (k["table"] for k in sinks
                 if k["source_name"].lower() == tr["result_name"].lower()),
                "",
            )
        if not dst and len(sinks) == 1:
            dst = sinks[0]["table"]
        if not src or not dst:
            continue
        for edge in _transform_column_edges(tr, src, dst, logical):
            graph.add_column_edge(edge)


def _transform_column_edges(
    tr: dict[str, str],
    src: str,
    dst: str,
    logical: dict[str, str],
) -> list[ColumnEdge]:
    edges: list[ColumnEdge] = []
    for name, body in _blocks(tr["body"]):
        if name.lower().replace("-", "_") != "field_mapper":
            continue
        for src_col, dst_col in _kv_pairs(body, raw_keys=True):
            edges.append(ColumnEdge(
                src, src_col, dst, dst_col,
                source="seatunnel", confidence="high",
            ))
    if edges:
        return edges
    query = tr["query"]
    if not query:
        return []
    parsed = extract_column_edges(query, target=dst, sources=[src])
    if not parsed:
        return []
    for e in parsed:
        # 查询里引用的是逻辑表名（result_table_name），映射回物理表
        e.src_table = logical.get(e.src_table.lower(), src)
        e.source = "seatunnel"
        e.confidence = "medium"
    return parsed


def from_seatunnel_files(
    paths: list[Path] | list[str],
) -> tuple[LineageGraph, list[str]]:
    """Never raises on a bad config — it is skipped with a warning instead."""
    graph = LineageGraph()
    warnings: list[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            warnings.append(f"无法读取 {path}: {exc}")
            continue
        try:
            _load_config(graph, text, origin=f"seatunnel:{path.name}")
        except Exception as exc:  # noqa: BLE001 — one bad config must not kill the build
            warnings.append(f"解析 {path} 失败: {exc}")
    return graph, warnings


def from_seatunnel_dir(directory: str | Path) -> tuple[LineageGraph, list[str]]:
    files = collect_seatunnel_files(directory)
    if not files:
        return LineageGraph(), [f"目录 {directory} 下没有找到 SeaTunnel 配置文件（*.conf/*.config/*.json）"]
    return from_seatunnel_files(files)
