# -*- coding: utf-8 -*-
"""SeaTunnel HOCON config builder for generated sync jobs.

Builder functions rather than string.Template — the column list, the
optional masking transform and the sink block all vary structurally per
table. Blocks are wired with ``result_table_name`` / ``source_table_name``
(SeaTunnel 2.3.x; the newer ``plugin_input``/``plugin_output`` aliases are
back-compatible — a naming toggle is deferred).

Credentials and endpoints are emitted as ``${mysql_password}``-style
SeaTunnel variable placeholders (pass ``-i key=value`` at submit time) —
generated files never contain secrets. HOCON does not substitute inside
quoted strings, so the placeholders survive parsing verbatim.
"""

from __future__ import annotations

from .model import TableSpec
from .pii import PiiHit, mask_expr

SINK_TYPES = ("console", "doris", "starrocks", "hive")

_SRC = "src"
_MASKED = "masked"


def hq(s: str) -> str:
    """Escape for a double-quoted HOCON string."""
    return (s or "").replace("\\", "\\\\").replace('"', '\\"')


def build_config(spec: TableSpec, sink_type: str, hits: list[PiiHit],
                 strategy: str, parallelism: int = 2) -> str:
    masked_cols = {h.column for h in hits if h.masked}
    sink_input = _MASKED if masked_cols else _SRC
    parts = [
        _env_block(parallelism),
        _jdbc_source_block(spec),
        _sql_transform_block(spec, masked_cols, strategy),
        _sink_block(spec, sink_type, sink_input),
    ]
    return "\n".join(parts)


def _env_block(parallelism: int) -> str:
    return (
        "env {\n"
        '  job.mode = "BATCH"\n'
        f"  parallelism = {parallelism}\n"
        "}\n"
    )


def _jdbc_source_block(spec: TableSpec) -> str:
    cols = ", ".join(c.name for c in spec.columns)
    query = f"SELECT {cols} FROM {spec.full_name}"
    return (
        "source {\n"
        "  Jdbc {\n"
        '    url = "jdbc:mysql://${mysql_host}:${mysql_port}/'
        f'{hq(spec.database or "")}"\n'
        '    driver = "com.mysql.cj.jdbc.Driver"\n'
        '    user = "${mysql_user}"\n'
        '    password = "${mysql_password}"\n'
        f'    query = "{hq(query)}"\n'
        f'    result_table_name = "{_SRC}"\n'
        "  }\n"
        "}\n"
    )


def _sql_transform_block(spec: TableSpec, masked_cols: set[str],
                         strategy: str) -> str:
    if not masked_cols:
        return "transform {}\n"
    select = ", ".join(
        mask_expr(c.name, strategy) if c.name in masked_cols else c.name
        for c in spec.columns)
    query = f"SELECT {select} FROM {_SRC}"
    return (
        "transform {\n"
        "  Sql {\n"
        f'    source_table_name = "{_SRC}"\n'
        f'    result_table_name = "{_MASKED}"\n'
        f'    query = "{hq(query)}"\n'
        "  }\n"
        "}\n"
    )


def _sink_block(spec: TableSpec, sink_type: str, sink_input: str) -> str:
    db = hq(spec.database or "ods")
    table = hq(spec.name)
    src_line = f'    source_table_name = "{sink_input}"\n'
    if sink_type == "console":
        return "sink {\n  Console {\n" + src_line + "  }\n}\n"
    if sink_type == "doris":
        return (
            "sink {\n"
            "  Doris {\n"
            + src_line +
            '    fenodes = "${doris_fenodes}"\n'
            '    username = "${doris_user}"\n'
            '    password = "${doris_password}"\n'
            f'    "table.identifier" = "{db}.{table}"\n'
            '    "sink.enable-2pc" = "false"\n'
            '    "sink.label-prefix" = "' + f'sync_{table}' + '"\n'
            "  }\n"
            "}\n"
        )
    if sink_type == "starrocks":
        return (
            "sink {\n"
            "  StarRocks {\n"
            + src_line +
            '    nodeUrls = ["${sr_node_urls}"]\n'
            '    base-url = "jdbc:mysql://${sr_jdbc_host}:${sr_jdbc_port}"\n'
            '    username = "${sr_user}"\n'
            '    password = "${sr_password}"\n'
            f'    database = "{db}"\n'
            f'    table = "{table}"\n'
            "  }\n"
            "}\n"
        )
    if sink_type == "hive":
        return (
            "sink {\n"
            "  Hive {\n"
            + src_line +
            f'    table_name = "{db}.{table}"\n'
            '    metastore_uri = "${hive_metastore_uri}"\n'
            "  }\n"
            "}\n"
        )
    raise ValueError(f"不支持的 sink 类型: {sink_type}")
