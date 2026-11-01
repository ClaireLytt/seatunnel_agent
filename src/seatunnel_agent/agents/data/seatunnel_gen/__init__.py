"""作业配置生成 — 表 DDL + 连接器对 → 配置体检零错误的 job.conf 草稿.

Deterministic core: parse the DDL (schema_drift parser reused), resolve
both connectors against config_lint's catalog, and emit a complete
env/source/sink HOCON — database/table/topic parameters filled from the
table name, documented examples for the rest (each named as a
placeholder), STREAMING auto-selected for CDC sources — then lint it
with config_lint before returning, so the draft always parses and
misses no required parameter.  config_lint checks configs; this writes
them.  No database connection.
"""

from .generator import ConfigDraft, generate_config
from .report import render_markdown

__all__ = [
    "ConfigDraft",
    "generate_config",
    "render_markdown",
]
