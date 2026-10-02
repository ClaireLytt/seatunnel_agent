# -*- coding: utf-8 -*-
"""EN/ZH strings for SQL formatter reports and the /sqlfmt page."""

from __future__ import annotations

FMT_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "SQL Formatter",
        "rpt_stats": "statements {statements} · parse failures {failed}",
        "rpt_batch_stats": ("files {files} · would reformat {changed} · "
                            "written {written} · parse failures {failed}"),
        "rpt_unchanged": "Already formatted — no changes.",
        "rpt_formatted": "Formatted SQL",
        "rpt_diff": "Diff",
        "rpt_errors": "Parse errors (statements kept verbatim)",
        "rpt_select_star": "style: bare SELECT * ×{n}",
        "rpt_changed": "would reformat",
        "rpt_clean": "ok",
        "rpt_written": "written",
        "rpt_disclaimer": (
            "> Deterministic sqlglot pretty-print — statements that do not "
            "parse are kept verbatim, formatting never destroys content."),
    },
    "zh": {
        "rpt_title": "SQL 格式化",
        "rpt_stats": "语句 {statements} · 解析失败 {failed}",
        "rpt_batch_stats": ("文件 {files} · 需格式化 {changed} · "
                            "已写回 {written} · 解析失败 {failed}"),
        "rpt_unchanged": "已经是规范格式 — 无需改动。",
        "rpt_formatted": "格式化结果",
        "rpt_diff": "差异",
        "rpt_errors": "解析失败（语句原样保留）",
        "rpt_select_star": "风格提示: 裸 SELECT * ×{n}",
        "rpt_changed": "需格式化",
        "rpt_clean": "规范",
        "rpt_written": "已写回",
        "rpt_disclaimer": (
            "> 基于 sqlglot 的确定性格式化 — 解析失败的语句原样保留，"
            "格式化永不破坏内容。"),
    },
}


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


def tp(lang: str, key: str) -> str:
    lang = normalize_lang(lang)
    return FMT_I18N.get(lang, {}).get(key) or FMT_I18N["zh"].get(key, key)
