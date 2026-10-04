"""DQC execution: deterministic check SQL, history-based fluctuation,
markdown report, optional Feishu push.

Every check compiles to a single SELECT aggregate (portable across the
supported executors), goes through validate_sql when a schema store is
present, and never writes anything.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..text2sql.subscriptions import builtin_params
from .rules import DQCCheck, DQCRule

_HISTORY_ENV = "DQC_HISTORY_PATH"
_DEFAULT_HISTORY = "logs/dqc_history.jsonl"


# ----------------------------------------------------------------------
# Check SQL builders (pure functions)
# ----------------------------------------------------------------------


def _where_clause(rule: DQCRule) -> str:
    if not rule.where:
        return ""
    text = rule.where
    for key, value in builtin_params().items():
        text = text.replace("${" + key + "}", value)
    return f"\nWHERE {text}"


def build_check_sql(rule: DQCRule, check: DQCCheck) -> str:
    where = _where_clause(rule)
    if check.type == "row_count":
        return f"SELECT COUNT(*) AS cnt FROM {rule.table}{where}"
    if check.type == "null_rate":
        col = check.column
        return (
            f"SELECT SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) * 100.0 "
            f"/ COUNT(*) AS null_pct FROM {rule.table}{where}"
        )
    if check.type == "unique":
        cols = ", ".join(check.columns)
        return (
            "SELECT COUNT(*) AS dup_groups FROM (\n"
            f"  SELECT {cols} FROM {rule.table}{where}\n"
            f"  GROUP BY {cols} HAVING COUNT(*) > 1\n"
            ") d"
        )
    if check.type == "enum_domain":
        allowed = ", ".join(f"'{a}'" for a in check.allowed)
        return (
            f"SELECT COUNT(*) AS bad_cnt FROM {rule.table}{where or ''}"
            f"{' AND' if where else chr(10) + 'WHERE'} "
            f"{check.column} IS NOT NULL AND {check.column} NOT IN ({allowed})"
        )
    raise ValueError(f"Unknown check type: {check.type}")


# ----------------------------------------------------------------------
# History (for row_count fluctuation)
# ----------------------------------------------------------------------


class DQCHistory:
    """JSONL of past check values; only the latest value per key matters."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            path = os.getenv(_HISTORY_ENV, _DEFAULT_HISTORY)
        self.path = Path(path)
        self._lock = threading.Lock()

    def last_value(self, key: str) -> float | None:
        with self._lock:
            if not self.path.is_file():
                return None
            value = None
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("key") == key:
                    value = rec.get("value")
            return float(value) if value is not None else None

    def record(self, key: str, value: float) -> None:
        rec = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "key": key,
            "value": value,
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def clear(self) -> None:
        with self._lock:
            if self.path.is_file():
                fd, tmp = tempfile.mkstemp(dir=str(self.path.parent))
                os.close(fd)
                os.replace(tmp, str(self.path))


# ----------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------


@dataclass
class CheckResult:
    table: str
    check_type: str
    status: str          # "pass" | "fail" | "error"
    actual: float | None = None
    detail: str = ""
    sql: str = ""


def _scalar(columns: list[str], rows: list[tuple]) -> float:
    if not rows or rows[0][-1] is None:
        return 0.0
    return float(rows[0][-1])


def _evaluate(
    rule: DQCRule, check: DQCCheck, value: float, history: DQCHistory,
) -> CheckResult:
    r = CheckResult(table=rule.table, check_type=check.type, actual=value,
                    status="pass")
    if check.type == "row_count":
        problems = []
        if check.min is not None and value < check.min:
            problems.append(f"行数 {value:g} < 下限 {check.min:g}")
        if check.max is not None and value > check.max:
            problems.append(f"行数 {value:g} > 上限 {check.max:g}")
        if check.max_change_pct is not None:
            key = f"{rule.table}|row_count|{rule.where}"
            last = history.last_value(key)
            history.record(key, value)
            if last is not None and last > 0:
                change = abs(value - last) / last * 100
                if change > check.max_change_pct:
                    problems.append(
                        f"波动 {change:.1f}% 超过阈值 "
                        f"{check.max_change_pct:g}%（上次 {last:g}）"
                    )
        if problems:
            r.status, r.detail = "fail", "; ".join(problems)
    elif check.type == "null_rate":
        if value > (check.max_pct or 0):
            r.status = "fail"
            r.detail = (f"{check.column} 空值率 {value:.2f}% > "
                        f"阈值 {check.max_pct:g}%")
    elif check.type == "unique":
        if value > 0:
            r.status = "fail"
            r.detail = (f"({', '.join(check.columns)}) 存在 "
                        f"{value:g} 组重复值")
    elif check.type == "enum_domain":
        if value > 0:
            r.status = "fail"
            r.detail = (f"{check.column} 有 {value:g} 行超出枚举域 "
                        f"{list(check.allowed)}")
    return r


def run_checks(
    rules: list[DQCRule],
    executor,
    schema_store=None,
    history: DQCHistory | None = None,
    ds_type: str = "hive",
) -> list[CheckResult]:
    """Run every check; execution errors become status='error' results."""
    from ..text2sql.validator import enforce_limit, validate_sql

    history = history or DQCHistory()
    results: list[CheckResult] = []
    for rule in rules:
        for check in rule.checks:
            sql = build_check_sql(rule, check)
            result = CheckResult(table=rule.table, check_type=check.type,
                                 status="error", sql=sql)
            if schema_store is not None:
                validation = validate_sql(sql, schema_store)
                if not validation.ok:
                    result.detail = "SQL rejected: " + "; ".join(validation.errors)
                    results.append(result)
                    continue
            try:
                qr = executor.run(enforce_limit(sql, dialect=ds_type), max_rows=10)
            except Exception as exc:
                from ..text2sql.tools import _sanitize_db_error

                result.detail = _sanitize_db_error(str(exc))
                results.append(result)
                continue
            evaluated = _evaluate(rule, check, _scalar(qr.columns, qr.rows), history)
            evaluated.sql = sql
            results.append(evaluated)
    return results


def render_report(results: list[CheckResult]) -> str:
    """Markdown DQC report (zh)."""
    total = len(results)
    failed = [r for r in results if r.status == "fail"]
    errored = [r for r in results if r.status == "error"]
    lines = ["# DQC 数据质量报告", ""]
    lines.append(
        f"共 {total} 项检查：✅ 通过 {total - len(failed) - len(errored)} · "
        f"❌ 不通过 {len(failed)} · ⚠️ 执行异常 {len(errored)}"
    )
    if failed or errored:
        lines.append("")
        lines.append("| 表 | 检查 | 状态 | 实测 | 说明 |")
        lines.append("|---|---|---|---|---|")
        for r in failed + errored:
            mark = "❌" if r.status == "fail" else "⚠️"
            actual = f"{r.actual:g}" if r.actual is not None else "-"
            lines.append(
                f"| {r.table} | {r.check_type} | {mark} | {actual} "
                f"| {r.detail} |"
            )
    return "\n".join(lines)


def push_failures(results: list[CheckResult], webhook_url: str) -> tuple[bool, str]:
    """Push a red card when any check failed/errored (silent when all pass)."""
    bad = [r for r in results if r.status != "pass"]
    if not bad or not webhook_url:
        return True, "no push needed"
    from ..text2sql.subscriptions import push_feishu

    body_lines = [
        f"- {r.table} · {r.check_type}: {r.detail}" for r in bad[:10]
    ]
    if len(bad) > 10:
        body_lines.append(f"... 共 {len(bad)} 项未通过")
    return push_feishu(
        webhook_url, "❌ DQC 数据质量告警", "\n".join(body_lines), ok=False,
    )


def results_to_dict(results: list[CheckResult]) -> list[dict[str, Any]]:
    return [
        {
            "table": r.table, "check": r.check_type, "status": r.status,
            "actual": r.actual, "detail": r.detail,
        }
        for r in results
    ]
