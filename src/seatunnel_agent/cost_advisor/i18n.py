# -*- coding: utf-8 -*-
"""EN/ZH strings for cost advisor reports and the /cost page."""

from __future__ import annotations

COST_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Query Cost Advisor",
        "rpt_window": ("window {days}d · records {records} · successful "
                       "{success} · total exec {total_s}s"),
        "rpt_empty": ("No audit records in the window — nothing to "
                      "analyze. Run some queries first (or point --qlog at "
                      "the right file)."),
        "rpt_top": "Top expensive query templates",
        "rpt_top_cols": ("| # | total ms | runs | avg ms | max ms | rows | "
                         "tables | patterns |"),
        "rpt_tables": "Per-table scan cost",
        "rpt_tables_cols": "| table | queries | total ms |",
        "rpt_nofilter": "Queries missing a partition filter",
        "rpt_nofilter_note": ("Partition columns checked: {cols}. A full "
                              "scan on a partitioned table is usually the "
                              "single biggest avoidable cost."),
        "rpt_none": "none",
        "rpt_disclaimer": (
            "> Recommendations only — computed from the query audit log; "
            "no table is touched and nothing is executed. Pattern tags "
            "come from the data-skew static rules."),
    },
    "zh": {
        "rpt_title": "查询成本顾问",
        "rpt_window": ("窗口 {days} 天 · 记录 {records} 条 · 成功 {success} 条 "
                       "· 总耗时 {total_s} 秒"),
        "rpt_empty": ("窗口内没有审计记录 — 无可分析数据。"
                      "请先执行一些查询（或用 --qlog 指定正确的日志文件）。"),
        "rpt_top": "Top 烧钱查询模板",
        "rpt_top_cols": ("| # | 总耗时 ms | 次数 | 平均 ms | 最大 ms | 行数 | "
                         "涉及表 | 昂贵模式 |"),
        "rpt_tables": "按表聚合的扫描成本",
        "rpt_tables_cols": "| 表 | 查询次数 | 总耗时 ms |",
        "rpt_nofilter": "缺少分区过滤的查询",
        "rpt_nofilter_note": ("检查的分区列：{cols}。分区表全表扫描通常是"
                              "最大的一笔可避免成本。"),
        "rpt_none": "无",
        "rpt_disclaimer": (
            "> 仅输出建议 — 基于查询审计日志计算；不触碰任何表、"
            "不执行任何语句。昂贵模式标签来自数据倾斜静态规则。"),
    },
}


def normalize_lang(lang: str | None) -> str:
    lang = (lang or "zh").strip().lower()
    return "en" if lang.startswith("en") else "zh"
