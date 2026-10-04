"""DQC — table-level data quality checks (rules YAML + deterministic SQL).

Check types: row_count (min/max + change vs the last run), null_rate,
unique, enum_domain. Pure SELECT aggregates through the shared executor
stack; violations optionally push a Feishu card; exit-code gate for CI.
"""

from .rules import DQCRule, load_rules, validate_rules
from .runner import CheckResult, DQCHistory, render_report, run_checks

__all__ = [
    "DQCRule", "load_rules", "validate_rules",
    "CheckResult", "DQCHistory", "run_checks", "render_report",
]
