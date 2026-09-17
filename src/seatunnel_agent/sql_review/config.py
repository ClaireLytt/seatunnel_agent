"""User rule configuration for the SQL review linter (.sqlreview.yaml).

Example file::

    partition_columns: [pt, dt, ds]
    incremental_suffixes: [_di, _df]
    disable: [readability, data_skew]
    severity:
      resource_usage: suggestion
    fail_on: critical
    custom_rules:
      - pattern: '\\border\\s+by\\b'
        message: 禁止在离线任务中使用 ORDER BY
        severity: risk            # 可选，默认 suggestion
        category: resource_usage  # 可选，默认 readability
        suggestion: 改用 SORT BY  # 可选
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .report import CHECK_CATALOG, Severity

DEFAULT_PARTITION_COLS = ("pt", "dt", "ds", "day", "date_p", "bizdate", "partition_date")
DEFAULT_INCREMENTAL_SUFFIXES = ("_di", "_hi", "_ri", "_df", "_hf", "_mi", "_wi")

CONFIG_FILENAMES = (".sqlreview.yaml", ".sqlreview.yml")

_SEVERITY_VALUES = {s.value for s in Severity}


@dataclass(frozen=True)
class CustomRule:
    """Project-specific regex rule from ``custom_rules`` in .sqlreview.yaml."""

    pattern: str
    message: str
    severity: Severity = Severity.SUGGESTION
    category: str = "readability"
    suggestion: str = ""

    @property
    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.pattern, re.IGNORECASE)


@dataclass
class ReviewConfig:
    partition_cols: tuple[str, ...] = DEFAULT_PARTITION_COLS
    incremental_suffixes: tuple[str, ...] = DEFAULT_INCREMENTAL_SUFFIXES
    disabled_categories: frozenset[str] = frozenset()
    severity_overrides: dict[str, Severity] = field(default_factory=dict)
    fail_on: str | None = None
    custom_rules: tuple[CustomRule, ...] = ()
    source_path: str | None = None


DEFAULT_CONFIG = ReviewConfig()


def _as_str_tuple(value: Any, key: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"'{key}' 必须是字符串列表")
    items = tuple(v.strip().lower() for v in value if v.strip())
    if not items:
        raise ValueError(f"'{key}' 不能为空列表")
    return items


def _parse_config(data: dict[str, Any], path: str | None = None) -> ReviewConfig:
    cfg = ReviewConfig(source_path=path)
    unknown = set(data) - {
        "partition_columns", "incremental_suffixes", "disable", "severity",
        "fail_on", "custom_rules",
    }
    if unknown:
        raise ValueError(f"未知配置项: {', '.join(sorted(unknown))}")

    if "partition_columns" in data:
        cfg.partition_cols = _as_str_tuple(data["partition_columns"], "partition_columns")
    if "incremental_suffixes" in data:
        cfg.incremental_suffixes = _as_str_tuple(
            data["incremental_suffixes"], "incremental_suffixes"
        )
    if "disable" in data:
        cats = _as_str_tuple(data["disable"], "disable")
        bad = [c for c in cats if c not in CHECK_CATALOG]
        if bad:
            raise ValueError(
                f"disable 中的未知检查类别: {', '.join(bad)}"
                f"（有效值: {', '.join(CHECK_CATALOG)}）"
            )
        cfg.disabled_categories = frozenset(cats)
    if "severity" in data:
        overrides = data["severity"]
        if not isinstance(overrides, dict):
            raise ValueError("'severity' 必须是 {类别: 级别} 映射")
        for cat, sev in overrides.items():
            if cat not in CHECK_CATALOG:
                raise ValueError(f"severity 中的未知检查类别: {cat}")
            if not isinstance(sev, str) or sev.lower() not in _SEVERITY_VALUES:
                raise ValueError(
                    f"severity.{cat} 的级别无效: {sev}"
                    f"（有效值: {', '.join(sorted(_SEVERITY_VALUES))}）"
                )
            cfg.severity_overrides[cat] = Severity(sev.lower())
    if "fail_on" in data:
        fo = data["fail_on"]
        if not isinstance(fo, str) or fo.lower() not in _SEVERITY_VALUES:
            raise ValueError(f"fail_on 的级别无效: {fo}")
        cfg.fail_on = fo.lower()
    if "custom_rules" in data:
        cfg.custom_rules = _parse_custom_rules(data["custom_rules"])
    return cfg


_CUSTOM_RULE_KEYS = {"pattern", "message", "severity", "category", "suggestion"}


def _parse_custom_rules(raw: Any) -> tuple[CustomRule, ...]:
    if not isinstance(raw, list):
        raise ValueError("'custom_rules' 必须是规则列表")
    rules: list[CustomRule] = []
    for i, item in enumerate(raw, 1):
        where = f"custom_rules[{i}]"
        if not isinstance(item, dict):
            raise ValueError(f"{where} 必须是映射（含 pattern 和 message）")
        unknown = set(item) - _CUSTOM_RULE_KEYS
        if unknown:
            raise ValueError(f"{where} 中的未知字段: {', '.join(sorted(unknown))}")
        pattern = item.get("pattern")
        message = item.get("message")
        if not isinstance(pattern, str) or not pattern.strip():
            raise ValueError(f"{where} 缺少 pattern")
        if not isinstance(message, str) or not message.strip():
            raise ValueError(f"{where} 缺少 message")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"{where} 的 pattern 无效: {exc}") from exc
        sev = item.get("severity", Severity.SUGGESTION.value)
        if not isinstance(sev, str) or sev.lower() not in _SEVERITY_VALUES:
            raise ValueError(f"{where} 的 severity 无效: {sev}")
        cat = item.get("category", "readability")
        if not isinstance(cat, str) or cat.lower() not in CHECK_CATALOG:
            raise ValueError(f"{where} 的未知检查类别: {cat}")
        rules.append(CustomRule(
            pattern=pattern, message=message.strip(),
            severity=Severity(sev.lower()), category=cat.lower(),
            suggestion=str(item.get("suggestion", "")).strip(),
        ))
    return tuple(rules)


def load_review_config(
    path: str | Path | None = None, cwd: str | Path | None = None
) -> ReviewConfig:
    """Load rule config from *path*, or auto-discover in *cwd* (default: '.').

    Returns DEFAULT_CONFIG when no file is found. Raises ValueError on an
    invalid file.
    """
    file: Path | None = None
    if path is not None:
        file = Path(path)
        if not file.is_file():
            raise ValueError(f"规则配置文件不存在: {file}")
    else:
        base = Path(cwd) if cwd is not None else Path(".")
        for name in CONFIG_FILENAMES:
            candidate = base / name
            if candidate.is_file():
                file = candidate
                break
    if file is None:
        return DEFAULT_CONFIG

    try:
        import yaml
    except ImportError as exc:
        raise ValueError(
            "读取 .sqlreview.yaml 需要 PyYAML: pip install pyyaml"
        ) from exc

    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"规则配置文件解析失败 ({file}): {exc}") from exc
    if data is None:
        return ReviewConfig(source_path=str(file))
    if not isinstance(data, dict):
        raise ValueError(f"规则配置文件 {file} 的顶层必须是映射")
    return _parse_config(data, path=str(file))
