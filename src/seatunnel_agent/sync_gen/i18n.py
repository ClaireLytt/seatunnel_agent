# -*- coding: utf-8 -*-
"""EN/ZH strings for sync generator manifests and the /syncgen page."""

from __future__ import annotations

SYNC_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Whole-Database Sync Generator",
        "rpt_source_ddl": "source: DDL {path}",
        "rpt_source_live": "source: live MySQL database {database}",
        "rpt_sink": "sink: {sink}",
        "rpt_filters": "filters: include={include} exclude={exclude}",
        "rpt_summary": ("tables {tables} · columns {columns} · PII columns "
                        "{pii} (masked {masked}) · warnings {warnings} · "
                        "unmapped types {unmapped}"),
        "rpt_tables": "Generated tables",
        "rpt_tables_cols": "| table | columns | primary key | PII columns | warnings |",
        "rpt_skipped": "Skipped tables",
        "rpt_warnings": "Warnings",
        "rpt_none": "none",
        "rpt_empty": "No tables found — check the DDL input and filters.",
        "rpt_pii_off_hint": ("PII columns detected but masking is OFF — "
                             "re-run with --pii to inject masking transforms."),
        "rpt_disclaimer": (
            "> Generated configs contain ${var} placeholders instead of "
            "credentials — pass real values at submit time "
            "(`-i mysql_password=...`). Review DDL before executing."),
    },
    "zh": {
        "rpt_title": "全库同步生成器",
        "rpt_source_ddl": "数据源：DDL 文件 {path}",
        "rpt_source_live": "数据源：在线 MySQL 库 {database}",
        "rpt_sink": "目标端：{sink}",
        "rpt_filters": "过滤：include={include} exclude={exclude}",
        "rpt_summary": ("表 {tables} 张 · 列 {columns} 个 · PII 列 {pii} 个"
                        "（已脱敏 {masked}）· 警告 {warnings} 条 · "
                        "未映射类型 {unmapped} 个"),
        "rpt_tables": "生成的表",
        "rpt_tables_cols": "| 表 | 列数 | 主键 | PII 列 | 警告 |",
        "rpt_skipped": "跳过的表",
        "rpt_warnings": "警告",
        "rpt_none": "无",
        "rpt_empty": "没有找到任何表 — 请检查 DDL 输入和过滤条件。",
        "rpt_pii_off_hint": ("检测到 PII 列但脱敏未开启 — 建议加 --pii "
                             "重新生成以注入脱敏 transform。"),
        "rpt_disclaimer": (
            "> 生成的配置使用 ${var} 占位符而非真实凭据 — 提交任务时传入 "
            "（`-i mysql_password=...`）。建表 DDL 请人工复核后再执行。"),
    },
}


def normalize_lang(lang: str | None) -> str:
    lang = (lang or "zh").strip().lower()
    return "en" if lang.startswith("en") else "zh"
