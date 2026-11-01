"""质量规则草稿 — 表样例 → DQC 可直接加载的 rules.yaml.

Deterministic core: profile the pasted sample (sample_profile reused)
and promise only what the data already keeps — a row_count change
guard, per-column null_rate caps with head-room, unique checks on
key-shaped fully-distinct columns, enum_domain pins on low-cardinality
columns — rendered as YAML that round-trips through the data_quality
rule parser.  sample_profile reports the shape; data_quality runs the
rules; this bridges them.  No database connection.
"""

from .generator import RuleDraft, generate_rules
from .report import render_markdown

__all__ = [
    "RuleDraft",
    "generate_rules",
    "render_markdown",
]
