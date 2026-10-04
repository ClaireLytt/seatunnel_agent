# -*- coding: utf-8 -*-
"""EN/ZH strings for test-data generation reports and the /testgen page."""

from __future__ import annotations

TGN_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "SQL Test Data Generator",
        "rpt_dialect": "dialect",
        "rpt_stats": "tables {tables} · rows per table {rows}",
        "rpt_table": "Table",
        "rpt_columns": "columns",
        "rpt_from_ddl": "from DDL",
        "rpt_inferred": "inferred",
        "rpt_csv": "CSV",
        "rpt_insert": "INSERT statements",
        "rpt_create": "CREATE TABLE",
        "rpt_notes": "Notes",
        "rpt_warnings": "Warnings",
        "rpt_validation": "SQLite validation",
        "val_ok": "query executed OK, returned {n} row(s)",
        "val_transpile_error": "not translatable to SQLite (inconclusive): {detail}",
        "val_exec_error": "execution failed on SQLite (inconclusive): {detail}",
        "val_skipped": "validation skipped: {detail}",
        "val_zero_rows": "⚠️ the query returned 0 rows on the generated "
                         "data — check filters vs. generated values",
        "rpt_disclaimer": (
            "> Deterministic generation — join columns share value pools "
            "and WHERE literals are satisfied, so the query exercises real "
            "paths. SQLite validation is best-effort: engine-specific "
            "functions may not translate."),
    },
    "zh": {
        "rpt_title": "SQL 测试数据生成",
        "rpt_dialect": "方言",
        "rpt_stats": "表 {tables} · 每表行数 {rows}",
        "rpt_table": "表",
        "rpt_columns": "列",
        "rpt_from_ddl": "来自 DDL",
        "rpt_inferred": "按用法推断",
        "rpt_csv": "CSV",
        "rpt_insert": "INSERT 语句",
        "rpt_create": "CREATE TABLE",
        "rpt_notes": "说明",
        "rpt_warnings": "警告",
        "rpt_validation": "SQLite 验证",
        "val_ok": "查询执行成功，返回 {n} 行",
        "val_transpile_error": "无法翻译为 SQLite（结果不确定）: {detail}",
        "val_exec_error": "SQLite 执行失败（结果不确定）: {detail}",
        "val_skipped": "跳过验证: {detail}",
        "val_zero_rows": "⚠️ 查询在生成数据上返回 0 行 — 请核对过滤条件与生成值",
        "rpt_disclaimer": (
            "> 确定性生成 — 关联列共享取值池、WHERE 字面量被满足，"
            "查询会跑到真实路径。SQLite 验证为尽力而为：引擎特有函数可能无法翻译。"),
    },
}


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


def tp(lang: str, key: str) -> str:
    lang = normalize_lang(lang)
    return TGN_I18N.get(lang, {}).get(key) or TGN_I18N["zh"].get(key, key)
