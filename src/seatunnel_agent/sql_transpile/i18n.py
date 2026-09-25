# -*- coding: utf-8 -*-
"""EN/ZH strings for SQL transpile reports and the /transpile page.

Same pattern as ``sql_review.i18n``: one flat dict per language, looked up
via ``tp(lang, key)`` with Chinese as the fallback.  Issue messages and
suggestions are templates keyed by ``Issue.kind`` and formatted with
``Issue.params`` at render time, so the deterministic core stays
language-free.
"""

from __future__ import annotations

TP_I18N: dict[str, dict[str, str]] = {
    "en": {
        # --- report chrome ---
        "rpt_title": "SQL Dialect Translation",
        "rpt_result": "Translation result",
        "rpt_issues": "Incompatibilities",
        "rpt_no_issues": "No incompatibilities found — fully automatic.",
        "rpt_stats": "statements {total} · auto {auto} · manual {manual} · failed {failed}",
        "rpt_batch_stats": "files {files} · statements {total} · auto {auto} · manual {manual} · failed {failed}",
        "rpt_src_inferred": "source dialect inferred as",
        "rpt_disclaimer": (
            "> Machine translation — review before running in production; "
            "consider the Data Comparison page to verify result equivalence."
        ),
        "rpt_stmt": "Statement",
        "rpt_line": "line",
        "rpt_parse_failed": "parse failed — original kept",
        # --- issue messages, keyed by Issue.kind ---
        "msg_parse_error": "Cannot parse: {error}",
        "msg_unsupported": "Not supported by the target dialect: {detail}",
        "msg_unknown_function": (
            "Unknown function {func} — no equivalent confirmed in the target "
            "dialect, manual check required"
        ),
        "msg_write_hint": (
            "Source SQL uses {clause}; verify the target table's bucketing / "
            "sort strategy instead"
        ),
        "msg_lateral_view": (
            "LATERAL VIEW table-function support differs across engines — "
            "verify on the target"
        ),
        "msg_insert_partition": (
            "INSERT ... PARTITION write syntax differs — Doris/StarRocks "
            "route rows by the partition column value"
        ),
        "msg_storage_clause": (
            "CREATE TABLE carries {clauses} — rewrite storage/properties for "
            "the target engine (ENGINE/DISTRIBUTED BY/PROPERTIES)"
        ),
        # --- suggestions, keyed by Issue.kind (optional) ---
        "fix_parse_error": "Fix the syntax or translate this statement manually",
        "fix_unknown_function": "Map the UDF to a target built-in or register it",
        "fix_storage_clause": "Model the table with the target DDL, then re-point the INSERT",
    },
    "zh": {
        "rpt_title": "SQL 方言翻译",
        "rpt_result": "翻译结果",
        "rpt_issues": "不兼容点",
        "rpt_no_issues": "未发现不兼容点 — 可全自动迁移。",
        "rpt_stats": "语句 {total} · 全自动 {auto} · 需人工 {manual} · 失败 {failed}",
        "rpt_batch_stats": "文件 {files} · 语句 {total} · 全自动 {auto} · 需人工 {manual} · 失败 {failed}",
        "rpt_src_inferred": "源方言推断为",
        "rpt_disclaimer": (
            "> 机器翻译结果，上线前需人工复核；建议配合数据比对页验证结果等价。"
        ),
        "rpt_stmt": "语句",
        "rpt_line": "行",
        "rpt_parse_failed": "解析失败 — 保留原文",
        "msg_parse_error": "无法解析: {error}",
        "msg_unsupported": "目标方言不支持: {detail}",
        "msg_unknown_function": "未知函数 {func} — 目标方言中无法确认等价写法，需人工核对",
        "msg_write_hint": "源 SQL 含 {clause}，请改为确认目标表的分桶/排序策略",
        "msg_lateral_view": "LATERAL VIEW 表函数各引擎支持不同，请在目标引擎验证",
        "msg_insert_partition": (
            "INSERT ... PARTITION 写分区语法有差异 — Doris/StarRocks 按分区列值自动路由"
        ),
        "msg_storage_clause": (
            "建表语句含 {clauses} — 需按目标引擎改写存储与属性子句"
            "（ENGINE/DISTRIBUTED BY/PROPERTIES）"
        ),
        "fix_parse_error": "修正语法或人工翻译该语句",
        "fix_unknown_function": "将 UDF 映射为目标内置函数或在目标引擎注册",
        "fix_storage_clause": "先用目标 DDL 建模，再迁移 INSERT 语句",
    },
}


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


def tp(lang: str, key: str) -> str:
    lang = normalize_lang(lang)
    return TP_I18N.get(lang, {}).get(key) or TP_I18N["zh"].get(key, key)


def issue_message(lang: str, kind: str, params: dict[str, str]) -> str:
    tmpl = tp(lang, f"msg_{kind}")
    try:
        return tmpl.format(**params)
    except (KeyError, IndexError):
        return tmpl


def issue_suggestion(lang: str, kind: str) -> str:
    key = f"fix_{kind}"
    text = TP_I18N[normalize_lang(lang)].get(key) or TP_I18N["zh"].get(key)
    return text or ""
