# -*- coding: utf-8 -*-
"""Routable agent catalog for the orchestrator.

Two sources:

* the MCP toolbox's deterministic callables
  (:func:`seatunnel_agent.mcp_toolbox.build_tool_functions`,
  ``include_db=False`` — the chat entry gets zero DB/file attack surface;
  file-path tools are filtered out for the same reason), and
* thin wrappers over the inline cores not in the toolbox (sql_fmt,
  config_lint, schema_drift, pii_scan, sql_testgen).

Everything is string-in / markdown-out, deterministic, and safe to run from
a chat request.  Tool schemas are derived from the function signatures;
descriptions are the (bilingual) docstrings.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

# file-path toolbox tools stay out of the chat entry
_SKIP_TOOLS = {"skew_check_file"}

# where each capability lives in the Web UI (for no-key suggestions)
_PAGES = {
    "sql_review": "/sqlreview",
    "sql_transpile": "/transpile",
    "impact_diff": "/impact",
    "migrate_to_seatunnel": "/migrate",
    "skew_check": "/dataskew",
    "sql_fmt": "/sqlfmt",
    "config_lint": "/conflint",
    "schema_drift": "/schemadrift",
    "pii_scan": "/pii",
    "sql_testgen": "/testgen",
    "secret_scan": "/secretscan",
    "dep_check": "/depcheck",
    "release_notes": "/release",
    "ci_triage": "/ciinspect",
}

_TYPE_MAP = {str: "string", int: "integer", float: "number", bool: "boolean"}


@dataclass
class AgentSpec:
    name: str
    description: str
    run: Callable[..., str]
    input_schema: dict[str, Any] = field(default_factory=dict)
    page: str = ""


def _schema_from_fn(fn: Callable) -> dict[str, Any]:
    """Minimal JSON schema from a tool signature (str/int/float/bool params).

    functools.wraps on the toolbox wrappers keeps the real signature."""
    props: dict[str, Any] = {}
    required: list[str] = []
    for name, param in inspect.signature(fn).parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        ptype = "string"
        if param.annotation in _TYPE_MAP:
            ptype = _TYPE_MAP[param.annotation]
        elif param.default is not param.empty and param.default is not None:
            ptype = _TYPE_MAP.get(type(param.default), "string")
        props[name] = {"type": ptype}
        if param.default is param.empty:
            required.append(name)
    return {"type": "object", "properties": props, "required": required}


def _doc(fn: Callable) -> str:
    return " ".join((inspect.getdoc(fn) or "").split())


# ── inline wrappers over cores not in the toolbox ──────────────────────────

def _wrap_sql_fmt(sql: str, dialect: str = "hive", lang: str = "zh") -> str:
    """SQL 格式化：sqlglot 确定性排版,解析失败的语句原样保留。返回格式化
    结果与差异的 Markdown 报告。dialect 如 hive/spark/mysql。"""
    from ..sql_fmt import format_text, render_markdown
    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    return render_markdown(format_text(sql, dialect=dialect), lang)


def _wrap_config_lint(config: str, lang: str = "zh") -> str:
    """SeaTunnel 配置深度检查：对照内置连接器文档做参数级 lint —— 未知
    连接器/参数(给出 did-you-mean)、缺失必填项、类型与枚举校验等。
    入参为 HOCON 配置文本,只解析不执行。"""
    from ..config_lint.linter import lint_text
    from ..config_lint.report import render_markdown
    if not (config or "").strip():
        return "配置不能为空 / config must not be empty"
    return render_markdown(lint_text(config), lang)


def _wrap_schema_drift(old_ddl: str, new_ddl: str, dialect: str = "hive",
                       lang: str = "zh") -> str:
    """Schema 漂移检查:对比两份 DDL 脚本,每处结构变更按 breaking / risk /
    info 分级(删表删列、类型不兼容、分区变化、疑似重命名等)。"""
    from ..schema_drift.differ import diff_scripts
    from ..schema_drift.report import render_markdown
    if not (old_ddl or "").strip() or not (new_ddl or "").strip():
        return "需要同时提供旧/新 DDL / both old and new DDL are required"
    return render_markdown(diff_scripts(old_ddl, new_ddl, dialect=dialect),
                           lang)


def _wrap_pii_scan(sql: str, dialect: str = "hive", lang: str = "zh") -> str:
    """敏感数据扫描(PII):命名规则 × 字段血缘,识别手机号/身份证/银行卡等
    敏感列并标出未脱敏的下游扩散。入参为 SQL/DDL 脚本文本。"""
    from ..pii_scan.report import render_markdown
    from ..pii_scan.scanner import scan_sql_text
    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    return render_markdown(scan_sql_text(sql, dialect=dialect), lang)


def _wrap_sql_testgen(sql: str, ddl: str = "", rows: int = 20,
                      dialect: str = "hive", lang: str = "zh") -> str:
    """SQL 测试数据生成:关联感知造数(等值 join 列共享取值池、WHERE 条件
    可满足、混入边界行),并在内存 SQLite 上验证查询真的能跑通出数。"""
    from ..sql_testgen.generator import generate
    from ..sql_testgen.report import render_markdown
    from ..sql_testgen.validator import validate_with_sqlite
    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    result = generate(sql, ddl=ddl, rows=max(1, min(int(rows), 200)),
                      dialect=dialect)
    result.validation = validate_with_sqlite(result)
    return render_markdown(result, lang)


def _wrap_secret_scan(text: str, lang: str = "zh") -> str:
    """敏感凭证扫描:云厂商 token / 私钥块 / 明文密码与 API Key 赋值 /
    DSN 内嵌密码 / 高熵字符串。入参为代码或配置文本,预览自动脱敏。"""
    from ..secret_scan import ScanResult, render_markdown, scan_text
    if not (text or "").strip():
        return "文本不能为空 / text must not be empty"
    return render_markdown(
        ScanResult(findings=scan_text(text), files_scanned=1), lang)


def _wrap_dep_check(metadata: str, lang: str = "zh") -> str:
    """依赖体检:对 pyproject.toml 或 requirements.txt 文本做离线检查 ——
    声明未装、版本违反、未钉版本、重复冲突与 License 清单。"""
    from ..dep_check import (
        check, parse_pyproject_text, parse_requirements_text, render_markdown,
    )
    if not (metadata or "").strip():
        return "依赖声明不能为空 / metadata must not be empty"
    if "[project]" in metadata or "[build-system]" in metadata:
        reqs = parse_pyproject_text(metadata)
    else:
        reqs = parse_requirements_text(metadata)
    return render_markdown(check(reqs), lang)


def _wrap_release_notes(commit_log: str, current_version: str = "",
                        lang: str = "zh") -> str:
    """发布助手:按 conventional commits 分组生成 changelog 并给出语义化
    版本建议。入参为每行 `sha<TAB>subject` 的提交记录文本。"""
    from ..release_notes import build_notes, render_markdown
    if not (commit_log or "").strip():
        return "提交记录不能为空 / commit log must not be empty"
    return render_markdown(build_notes(commit_log, current_version), lang)


def _wrap_ci_triage(log_text: str, job_name: str = "job",
                    lang: str = "zh") -> str:
    """CI 日志诊断:把失败作业日志聚类成 Top-N 根因(数字/路径/哈希先
    掩码再分组)。入参为日志文本(带时间戳前缀也可以)。"""
    from ..ci_inspect import analyze, render_markdown
    if not (log_text or "").strip():
        return "日志不能为空 / log must not be empty"
    return render_markdown(analyze(logs={job_name: log_text}), lang)


_WRAPPERS: dict[str, Callable[..., str]] = {
    "sql_fmt": _wrap_sql_fmt,
    "config_lint": _wrap_config_lint,
    "schema_drift": _wrap_schema_drift,
    "pii_scan": _wrap_pii_scan,
    "sql_testgen": _wrap_sql_testgen,
    "secret_scan": _wrap_secret_scan,
    "dep_check": _wrap_dep_check,
    "release_notes": _wrap_release_notes,
    "ci_triage": _wrap_ci_triage,
}


def build_catalog(default_lang: str = "zh") -> dict[str, AgentSpec]:
    """Every routable agent, keyed by tool name."""
    from ..mcp_toolbox import build_tool_functions
    specs: dict[str, AgentSpec] = {}
    for name, fn in build_tool_functions(default_lang=default_lang,
                                         include_db=False).items():
        if name in _SKIP_TOOLS:
            continue
        specs[name] = AgentSpec(name=name, description=_doc(fn), run=fn,
                                input_schema=_schema_from_fn(fn),
                                page=_PAGES.get(name, ""))
    for name, fn in _WRAPPERS.items():
        specs[name] = AgentSpec(name=name, description=_doc(fn), run=fn,
                                input_schema=_schema_from_fn(fn),
                                page=_PAGES.get(name, ""))
    return specs


def tool_definitions(catalog: dict[str, AgentSpec]) -> list[dict[str, Any]]:
    """Anthropic-style tool list (LLMClient converts for OpenAI itself)."""
    return [{
        "name": spec.name,
        "description": spec.description,
        "input_schema": spec.input_schema,
    } for spec in catalog.values()]
