# -*- coding: utf-8 -*-
"""EN/ZH strings for caliber reconciliation reports and the /reconcile page."""

from __future__ import annotations

RECONCILE_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "SQL Caliber Reconciliation",
        "rpt_dialect": "dialect",
        "rpt_stats": ("findings {total} (critical {critical} / risk {risk} "
                      "/ info {info})"),
        "rpt_identical": ("No caliber difference found — the two statements "
                          "share sources, joins, filters and aggregation."),
        "rpt_parse_error": "Parse failed: {error}",
        "rpt_profiles": "Caliber profiles",
        "rpt_side_a": "SQL A",
        "rpt_side_b": "SQL B",
        "rpt_disclaimer": (
            "> Deterministic AST diff — no database connection, nothing "
            "executed. A caliber match does not guarantee identical data "
            "(freshness and runtime state still differ)."),
        "cat_source": "Source tables",
        "cat_join": "Joins",
        "cat_filter": "Filters",
        "cat_time_range": "Time range",
        "cat_aggregation": "Aggregation",
        "cat_dedup": "Deduplication",
        "cat_limit": "HAVING / LIMIT",
        "cat_output": "Output columns",
        "sev_critical": "critical",
        "sev_risk": "risk",
        "sev_info": "info",
        "msg_tables_differ": ("source tables differ — only in A: {only_a}; "
                              "only in B: {only_b}"),
        "msg_join_only": "join on {table} exists only in SQL {side}",
        "msg_join_type": "join type on {table}: A uses {a}, B uses {b}",
        "msg_join_cond": ("join condition on {table} differs — A: {a} | "
                          "B: {b}"),
        "msg_filter_only": "filter only in SQL {side}: {pred}",
        "msg_time_differ": "time range differs — A: {a} | B: {b}",
        "msg_agg_differ": "aggregate expressions differ — A: {a} | B: {b}",
        "msg_group_differ": "GROUP BY keys differ — A: {a} | B: {b}",
        "msg_dedup_differ": "dedup mechanism differs — A: {a}, B: {b}",
        "msg_having_differ": "HAVING differs — A: {a} | B: {b}",
        "msg_limit_differ": "LIMIT differs — A: {a} | B: {b}",
        "msg_output_differ": ("output-only difference — only in A: {only_a}; "
                              "only in B: {only_b}"),
    },
    "zh": {
        "rpt_title": "SQL 口径对账",
        "rpt_dialect": "方言",
        "rpt_stats": ("差异 {total} 项（严重 {critical} / 风险 {risk} "
                      "/ 提示 {info}）"),
        "rpt_identical": "未发现口径差异 — 两条 SQL 的数据源、JOIN、过滤与聚合一致。",
        "rpt_parse_error": "解析失败：{error}",
        "rpt_profiles": "口径画像",
        "rpt_side_a": "SQL A",
        "rpt_side_b": "SQL B",
        "rpt_disclaimer": (
            "> 确定性 AST 对比 — 不连接数据库、不执行任何语句。"
            "口径一致不代表结果一定相同（数据新鲜度等运行时因素仍可能不同）。"),
        "cat_source": "数据源",
        "cat_join": "关联 (JOIN)",
        "cat_filter": "过滤条件",
        "cat_time_range": "时间范围",
        "cat_aggregation": "聚合口径",
        "cat_dedup": "去重方式",
        "cat_limit": "HAVING / LIMIT",
        "cat_output": "输出列",
        "sev_critical": "严重",
        "sev_risk": "风险",
        "sev_info": "提示",
        "msg_tables_differ": ("数据源不同 — 仅 A 使用: {only_a}；"
                              "仅 B 使用: {only_b}"),
        "msg_join_only": "对 {table} 的 JOIN 仅存在于 SQL {side}",
        "msg_join_type": "对 {table} 的 JOIN 类型不同：A 为 {a}，B 为 {b}",
        "msg_join_cond": "对 {table} 的 JOIN 条件不同 — A: {a} | B: {b}",
        "msg_filter_only": "过滤条件仅存在于 SQL {side}: {pred}",
        "msg_time_differ": "时间范围不同 — A: {a} | B: {b}",
        "msg_agg_differ": "聚合表达式不同 — A: {a} | B: {b}",
        "msg_group_differ": "GROUP BY 维度不同 — A: {a} | B: {b}",
        "msg_dedup_differ": "去重方式不同 — A 用 {a}，B 用 {b}",
        "msg_having_differ": "HAVING 不同 — A: {a} | B: {b}",
        "msg_limit_differ": "LIMIT 不同 — A: {a} | B: {b}",
        "msg_output_differ": ("仅输出列不同（不影响聚合口径）— 仅 A: {only_a}；"
                              "仅 B: {only_b}"),
    },
}


def normalize_lang(lang: str | None) -> str:
    lang = (lang or "zh").strip().lower()
    return "en" if lang.startswith("en") else "zh"
