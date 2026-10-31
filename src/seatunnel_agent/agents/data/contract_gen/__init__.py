"""契约草稿生成 — CREATE TABLE DDL → contract_check 可消费的 YAML 草稿.

Deterministic core: parse the DDL (schema_drift parser reused), promise
only what each table already keeps — data columns with types, partition
layout, the comment rule (require_comments at high coverage, otherwise
pin existing comments) — and render YAML that round-trips through the
contract_check parser.  No database connection.
"""

from .generator import ContractDraft, TableDraft, generate_contract
from .report import render_markdown

__all__ = [
    "ContractDraft",
    "TableDraft",
    "generate_contract",
    "render_markdown",
]
