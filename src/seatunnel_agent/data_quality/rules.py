"""DQC rule definitions — YAML schema and load-time validation.

```yaml
version: 1
rules:
  - table: dc_test_orders_a
    where: "dt = '${yesterday_pt}'"     # optional filter (date macros ok)
    checks:
      - type: row_count
        min: 1                          # optional
        max: 1000000                    # optional
        max_change_pct: 50              # optional, vs the last recorded run
      - type: null_rate
        column: amount
        max_pct: 5
      - type: unique
        columns: [id]
      - type: enum_domain
        column: status
        allowed: [paid, refund]
```
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

CHECK_TYPES = ("row_count", "null_rate", "unique", "enum_domain")

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class DQCCheck:
    type: str
    column: str = ""
    columns: tuple[str, ...] = ()
    min: float | None = None
    max: float | None = None
    max_change_pct: float | None = None
    max_pct: float | None = None
    allowed: tuple[str, ...] = ()


@dataclass(frozen=True)
class DQCRule:
    table: str
    where: str = ""
    checks: tuple[DQCCheck, ...] = ()


@dataclass
class RuleErrors:
    errors: list[str] = field(default_factory=list)

    def add(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")


def _parse_check(raw: dict, where: str, errs: RuleErrors) -> DQCCheck | None:
    ctype = str(raw.get("type", "")).strip()
    if ctype not in CHECK_TYPES:
        errs.add(where, f"type 只支持 {', '.join(CHECK_TYPES)} (got '{ctype}')")
        return None

    def _num(key: str) -> float | None:
        v = raw.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            errs.add(where, f"{key} 必须是数字 (got {v!r})")
            return None

    check = DQCCheck(
        type=ctype,
        column=str(raw.get("column", "") or "").strip(),
        columns=tuple(str(c).strip() for c in (raw.get("columns") or [])
                      if str(c).strip()),
        min=_num("min"),
        max=_num("max"),
        max_change_pct=_num("max_change_pct"),
        max_pct=_num("max_pct"),
        allowed=tuple(str(a) for a in (raw.get("allowed") or [])),
    )
    if ctype == "row_count":
        if check.min is None and check.max is None and check.max_change_pct is None:
            errs.add(where, "row_count 至少需要 min/max/max_change_pct 之一")
    elif ctype == "null_rate":
        if not check.column:
            errs.add(where, "null_rate 需要 column")
        if check.max_pct is None:
            errs.add(where, "null_rate 需要 max_pct")
    elif ctype == "unique":
        if not check.columns:
            errs.add(where, "unique 需要 columns 列表")
    elif ctype == "enum_domain":
        if not check.column:
            errs.add(where, "enum_domain 需要 column")
        if not check.allowed:
            errs.add(where, "enum_domain 需要 allowed 取值列表")
        for a in check.allowed:
            if "'" in a:
                errs.add(where, f"allowed 取值不允许包含单引号: {a!r}")
    for col in (check.column, *check.columns):
        if col and not _IDENT_RE.match(col):
            errs.add(where, f"非法列名: {col!r}")
    return check


def parse_rules_text(text: str) -> tuple[list[DQCRule], list[str]]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise ValueError("解析 DQC 规则需要 PyYAML: pip install pyyaml") from exc
    errs = RuleErrors()
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [], [f"DQC 规则解析失败: {exc}"]
    if data is None:
        return [], []
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        return [], ["DQC 规则顶层必须是含 rules 列表的映射"]

    rules: list[DQCRule] = []
    for i, raw in enumerate(data["rules"]):
        where = f"rules[{i}]"
        if not isinstance(raw, dict):
            errs.add(where, "必须是映射")
            continue
        table = str(raw.get("table", "") or "").strip()
        if not table:
            errs.add(where, "缺少 table")
            continue
        where = f"table '{table}'"
        raw_checks = raw.get("checks")
        if not isinstance(raw_checks, list) or not raw_checks:
            errs.add(where, "缺少 checks 列表")
            continue
        before = len(errs.errors)
        checks = [c for c in (
            _parse_check(rc, f"{where} checks[{j}]", errs)
            for j, rc in enumerate(raw_checks)
            if isinstance(rc, dict)
        ) if c is not None]
        if len(errs.errors) > before or not checks:
            continue
        rules.append(DQCRule(
            table=table,
            where=str(raw.get("where", "") or "").strip(),
            checks=tuple(checks),
        ))
    return rules, errs.errors


def load_rules(path: str | Path) -> tuple[list[DQCRule], list[str]]:
    p = Path(path)
    if not p.is_file():
        return [], [f"DQC 规则文件不存在: {p}"]
    return parse_rules_text(p.read_text(encoding="utf-8"))


def validate_rules(rules: list[DQCRule], schema_store) -> list[str]:
    """Cross-check rules against the schema whitelist (table/columns exist)."""
    errors: list[str] = []
    for rule in rules:
        table = schema_store.get(rule.table)
        if table is None:
            errors.append(f"table '{rule.table}': 不在 schema 白名单中")
            continue
        all_cols = {c.name.lower()
                    for c in table.columns + table.partition_columns}
        for check in rule.checks:
            for col in (check.column, *check.columns):
                if col and col.lower() not in all_cols:
                    errors.append(
                        f"table '{rule.table}' {check.type}: 列 '{col}' 不存在"
                    )
    return errors
