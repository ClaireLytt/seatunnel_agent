# -*- coding: utf-8 -*-
"""Deterministic checkers for eval outputs.

Every check returns ``(passed, detail)``.  The optional LLM judge lives in
the runner (it needs a client); everything here is pure so the CI gate never
depends on a second model call.
"""

from __future__ import annotations

import json
import re

from .suite import Check


def extract_sql(output: str) -> str:
    """The SQL to validate: fenced ```sql blocks when present (joined),
    otherwise the whole output."""
    blocks = re.findall(r"```(?:sql)?\s*\n(.*?)```", output,
                        flags=re.DOTALL | re.IGNORECASE)
    return "\n".join(b.strip() for b in blocks) if blocks else output


def run_check(check: Check, output: str) -> tuple[bool, str]:
    t, v = check.type, check.value
    if t == "contains":
        return v in output, f"contains {v!r}"
    if t == "icontains":
        return v.lower() in output.lower(), f"icontains {v!r}"
    if t == "not_contains":
        return v not in output, f"not_contains {v!r}"
    if t == "regex":
        try:
            ok = re.search(v, output, flags=re.DOTALL) is not None
        except re.error as exc:
            return False, f"regex {v!r} 本身非法: {exc}"
        return ok, f"regex {v!r}"
    if t == "equals":
        return output.strip() == v.strip(), "equals"
    if t == "json_valid":
        try:
            json.loads(extract_json(output))
            return True, "json_valid"
        except ValueError as exc:
            return False, f"json_valid: {exc}"
    if t == "sql_valid":
        sql = extract_sql(output).strip()
        if not sql:
            return False, "sql_valid: 输出中没有 SQL"
        try:
            import sqlglot
            sqlglot.parse(sql, read=check.dialect)
            return True, f"sql_valid ({check.dialect})"
        except ImportError:
            return False, "sql_valid 需要 sqlglot: pip install sqlglot"
        except Exception as exc:  # noqa: BLE001 — sqlglot raises ParseError subclasses
            return False, f"sql_valid ({check.dialect}): {exc}"
    raise ValueError(f"unknown check type: {t}")  # judge handled by runner


def extract_json(output: str) -> str:
    """Fenced ```json block when present, else the whole output."""
    blocks = re.findall(r"```(?:json)?\s*\n(.*?)```", output,
                        flags=re.DOTALL | re.IGNORECASE)
    return blocks[0].strip() if blocks else output.strip()
