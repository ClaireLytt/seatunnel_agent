# -*- coding: utf-8 -*-
"""Eval suite loading & validation.

A suite is YAML::

    suite: text2sql-golden
    cases:
      - id: t1
        agent: raw_prompt | text2sql | sql_review
        input: {...}              # adapter-specific, see targets.py
        expect:
          - {type: contains, value: "GROUP BY"}
          - {type: sql_valid, dialect: hive}
        weight: 2                 # optional, default 1

Validation is strict and errors cite the case id — a silently skipped golden
case is a hole in the safety net.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CHECK_TYPES = ("contains", "icontains", "not_contains", "regex", "equals",
               "sql_valid", "json_valid", "judge")
# "judge" needs no value-free validation exemption: value = the rubric text.
_VALUE_FREE = ("sql_valid", "json_valid")


@dataclass
class Check:
    type: str
    value: str = ""
    dialect: str = "hive"   # sql_valid only

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "value": self.value,
                "dialect": self.dialect}


@dataclass
class Case:
    id: str
    agent: str
    input: dict[str, Any]
    expect: list[Check] = field(default_factory=list)
    weight: float = 1.0


@dataclass
class Suite:
    name: str
    cases: list[Case] = field(default_factory=list)


# NB: no angle brackets in the default source — the error text is shown in
# markdown components, where "<inline>" would be swallowed as an HTML tag.
def parse_suite(text: str, source: str = "(inline)") -> Suite:
    try:
        import yaml
    except ImportError:  # pragma: no cover - pyyaml ships with [all]/[dev]
        raise ValueError("评测套件需要 pyyaml: pip install pyyaml")
    try:
        raw = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"{source}: YAML 解析失败: {exc}")
    if not isinstance(raw, dict) or not isinstance(raw.get("cases"), list):
        raise ValueError(f"{source}: 期望顶层为 {{suite, cases: [...]}}")
    from .targets import TARGETS
    name = str(raw.get("suite") or Path(source).stem)
    cases: list[Case] = []
    seen: set[str] = set()
    for i, item in enumerate(raw["cases"]):
        if not isinstance(item, dict):
            raise ValueError(f"{source}: cases[{i}] 必须是对象")
        cid = str(item.get("id") or f"case-{i}")
        if cid in seen:
            raise ValueError(f"{source}: case id 重复: {cid}")
        seen.add(cid)
        agent = str(item.get("agent") or "")
        if agent not in TARGETS:
            raise ValueError(
                f"{source}: case {cid}: 未知 agent {agent!r}"
                f"(支持: {', '.join(sorted(TARGETS))})")
        inp = item.get("input")
        if not isinstance(inp, dict) or not inp:
            raise ValueError(f"{source}: case {cid}: input 必须是非空对象")
        raw_checks = item.get("expect")
        if not isinstance(raw_checks, list) or not raw_checks:
            raise ValueError(f"{source}: case {cid}: expect 必须是非空列表")
        checks: list[Check] = []
        for j, chk in enumerate(raw_checks):
            if not isinstance(chk, dict):
                raise ValueError(f"{source}: case {cid}: expect[{j}] 必须是对象")
            ctype = str(chk.get("type") or "")
            if ctype not in CHECK_TYPES:
                raise ValueError(
                    f"{source}: case {cid}: 未知检查类型 {ctype!r}"
                    f"(支持: {', '.join(CHECK_TYPES)})")
            value = chk.get("value", "")
            if ctype not in _VALUE_FREE and not str(value).strip():
                raise ValueError(
                    f"{source}: case {cid}: expect[{j}] ({ctype}) 缺少 value")
            checks.append(Check(type=ctype, value=str(value),
                                dialect=str(chk.get("dialect", "hive"))))
        try:
            weight = float(item.get("weight", 1.0))
        except (TypeError, ValueError):
            raise ValueError(f"{source}: case {cid}: weight 必须是数字")
        if weight <= 0:
            raise ValueError(f"{source}: case {cid}: weight 必须 > 0")
        cases.append(Case(id=cid, agent=agent, input=inp,
                          expect=checks, weight=weight))
    if not cases:
        raise ValueError(f"{source}: 套件没有任何 case")
    return Suite(name=name, cases=cases)


def load_suite(path: str | Path) -> Suite:
    p = Path(path)
    return parse_suite(p.read_text(encoding="utf-8"), source=str(p))
