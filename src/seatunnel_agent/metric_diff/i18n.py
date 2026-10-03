# -*- coding: utf-8 -*-
"""EN/ZH strings for metric consistency reports and the /metricdiff page."""

from __future__ import annotations

MDF_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Metric Consistency Check",
        "rpt_root": "root",
        "rpt_dialect": "dialect",
        "rpt_stats": ("output columns {metrics} · consistent {consistent} · "
                      "conflicts {total} (high {high} / medium {medium})"),
        "rpt_clean": "No caliber conflicts — same-named metrics agree.",
        "rpt_defined_in": "defined in",
        "rpt_from": "from",
        "rpt_warnings": "Warnings",
        "rpt_disclaimer": (
            "> Deterministic comparison over column-level lineage — "
            "expressions are canonicalized (aliases/qualifiers stripped, "
            "COUNT(1)≡COUNT(*)) before comparing. No database, no LLM."),
        "msg_expr_conflict": "same metric name, different formulas",
        "msg_source_conflict": "same name copied from different source columns",
    },
    "zh": {
        "rpt_title": "指标口径一致性检查",
        "rpt_root": "扫描目标",
        "rpt_dialect": "方言",
        "rpt_stats": ("输出列 {metrics} · 一致 {consistent} · "
                      "冲突 {total} (高 {high} / 中 {medium})"),
        "rpt_clean": "未发现口径冲突 — 同名指标定义一致。",
        "rpt_defined_in": "定义于",
        "rpt_from": "取自",
        "rpt_warnings": "警告",
        "rpt_disclaimer": (
            "> 基于列级血缘的确定性比对 — 表达式先做归一化"
            "（去别名/去表前缀、COUNT(1)≡COUNT(*)）再比较。"
            "不连数据库、不调用 LLM。"),
        "msg_expr_conflict": "同名指标，计算公式不同",
        "msg_source_conflict": "同名字段取自不同来源列",
    },
}


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


def tp(lang: str, key: str) -> str:
    lang = normalize_lang(lang)
    return MDF_I18N.get(lang, {}).get(key) or MDF_I18N["zh"].get(key, key)
