"""sqlglot-based AST checks: dialect-aware syntax validation.

Runs alongside the regex rules (dual-track): a parse failure becomes a
critical ``syntax`` finding, but the regex rules still lint the statement
so a typo does not hide every other problem. Degrades to a no-op when
sqlglot is not installed or has no reader for the dialect.
"""

from __future__ import annotations

import re

from .report import Finding, Severity

# review dialect -> sqlglot reader name; None = no reliable reader, skip
SQLGLOT_DIALECTS: dict[str, str | None] = {
    "hive": "hive",
    "spark": "spark",
    "flink": None,          # sqlglot has no Flink/Calcite dialect
    "maxcompute": "hive",   # MaxCompute SQL is hive-compatible
    "mysql": "mysql",
    "postgresql": "postgres",
    "sqlserver": "tsql",
    "clickhouse": "clickhouse",
    "doris": "doris",
    "sqlite": "sqlite",
}

_MAX_SYNTAX_FINDINGS = 3

# scheduler template variables (${bizdate}, ${yyyymmdd}) are not SQL; stand
# in a numeric literal so templated scripts still parse
_TEMPLATE_VAR_RE = re.compile(r"\$\{[^}]*\}")


def check_syntax(sql: str, dialect: str) -> list[Finding]:
    """Parse *sql* with the dialect-matched sqlglot reader; report failures."""
    reader = SQLGLOT_DIALECTS.get(dialect)
    if reader is None:
        return []
    try:
        import sqlglot
        from sqlglot.errors import ParseError
    except ImportError:
        return []

    text = _TEMPLATE_VAR_RE.sub("1", sql)
    try:
        sqlglot.parse(text, read=reader)
    except ParseError as exc:
        findings: list[Finding] = []
        errors = getattr(exc, "errors", None) or [{}]
        for err in errors[:_MAX_SYNTAX_FINDINGS]:
            desc = str(err.get("description") or exc).strip()
            line = err.get("line")
            findings.append(Finding(
                severity=Severity.CRITICAL,
                category="syntax",
                description=f"SQL 解析失败：{desc}",
                location=f"行 {line}" if line else "全局",
                impact="语句大概率无法执行",
                suggestion="先修正语法错误，再进行后续审查",
                key="syntax_error", args={"error": desc},
            ))
        return findings
    except Exception:
        # sqlglot internal failure must never break the linter
        return []
    return []
