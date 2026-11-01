"""EN/ZH strings for freshness reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

FRESHNESS_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Data Freshness Scan",
        "rpt_now": "evaluated at",
        "rpt_stats": ("tables {tables} · stalled {stalled} · stale {stale} · "
                      "late {late} · unknown {unknown} · ok {ok}"),
        "rpt_findings": "Findings",
        "rpt_col_table": "table",
        "rpt_col_verdict": "verdict",
        "rpt_col_last": "last updated",
        "rpt_col_age": "age",
        "rpt_col_interval": "cadence",
        "rpt_col_detail": "why",
        "verdict_stalled": "STALLED",
        "verdict_stale": "STALE",
        "verdict_late": "LATE",
        "verdict_unknown": "UNKNOWN",
        "verdict_ok": "ok",
        "detail_no_update": "no update for over {factor}x the cadence",
        "detail_over_max_age": "older than the max_age rule ({max_age})",
        "detail_gap_over_interval": ("last update arrived {gap} after the "
                                     "previous one (cadence {interval})"),
        "detail_no_cadence": "fewer than 3 updates and no rule — cannot judge",
        "src_rule": "rule",
        "src_inferred": "inferred",
        "rpt_ok_tables": "Healthy tables",
        "rpt_warnings": "Warnings",
        "rpt_all_ok": "Every table is fresh at the evaluated time.",
        "rpt_disclaimer": ("> Deterministic scan — cadence comes from rules "
                           "or the median historical gap; 'now' defaults to "
                           "the latest update seen, so runs are "
                           "reproducible. No database connection."),
    },
    "zh": {
        "rpt_title": "数据新鲜度监控",
        "rpt_now": "评估时刻",
        "rpt_stats": ("表 {tables} · 断更 {stalled} · 过期 {stale} · "
                      "迟到 {late} · 无法判定 {unknown} · 正常 {ok}"),
        "rpt_findings": "问题明细",
        "rpt_col_table": "表",
        "rpt_col_verdict": "判定",
        "rpt_col_last": "最近更新",
        "rpt_col_age": "数据年龄",
        "rpt_col_interval": "节奏",
        "rpt_col_detail": "原因",
        "verdict_stalled": "断更",
        "verdict_stale": "过期",
        "verdict_late": "迟到",
        "verdict_unknown": "无法判定",
        "verdict_ok": "正常",
        "detail_no_update": "超过 {factor} 倍节奏没有新产出",
        "detail_over_max_age": "数据年龄超过 max_age 规则（{max_age}）",
        "detail_gap_over_interval": ("最近一次产出距上一次 {gap}，"
                                     "超出节奏 {interval}"),
        "detail_no_cadence": "更新不足 3 次且无规则，无法判定节奏",
        "src_rule": "规则",
        "src_inferred": "推断",
        "rpt_ok_tables": "正常的表",
        "rpt_warnings": "警告",
        "rpt_all_ok": "评估时刻所有表均按时产出。",
        "rpt_disclaimer": ("> 确定性扫描 — 节奏来自规则或历史更新间隔的中位数；"
                           "now 默认取清单里最晚的更新时间，结果可复现。"
                           "不连数据库。"),
    },
}


tp = make_lookup(FRESHNESS_I18N)
