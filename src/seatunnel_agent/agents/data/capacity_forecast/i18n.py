"""EN/ZH strings for the capacity-forecast reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

CF_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Capacity Forecast",
        "rpt_scope": "quota **{quota:g}** · current total "
                     "**{total:g}** · growing **{growth:+g}/day** · "
                     "exhaustion **{exhaustion}**{days}",
        "rpt_days": " (~{d:g} day(s) left)",
        "rpt_findings": "Findings",
        "col_code": "code",
        "col_sev": "severity",
        "col_detail": "evidence",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "CF001": "quota exhaustion in ~{days_left:g} day(s) "
                 "({exhaustion_date}) — {total_latest:g} of {quota:g}, "
                 "{daily_growth:+g}/day",
        "CF002": "top growers — {top}",
        "CF003": "shrinking — {metrics}: reclaim is working",
        "rpt_trends": "Per-metric trend (fastest growth first)",
        "col_metric": "metric",
        "col_latest": "latest",
        "col_growth": "per day",
        "col_points": "points",
        "rpt_no_findings": "No horizon alarm — growth fits the quota.",
        "rpt_disclaimer": "> Least-squares slope over the last {window} "
                          "points, LINEAR extrapolation — a step change "
                          "invalidates the date. Alarm horizons 90/30 "
                          "days. Units follow your values (GB or rows). "
                          "No storage connection.",
        "rpt_llm_note": "Capacity note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "容量耗尽预测",
        "rpt_scope": "配额 **{quota:g}** · 当前总量 **{total:g}** · "
                     "增速 **{growth:+g}/天** · 预计耗尽 "
                     "**{exhaustion}**{days}",
        "rpt_days": "（约剩 {d:g} 天）",
        "rpt_findings": "发现",
        "col_code": "编码",
        "col_sev": "级别",
        "col_detail": "证据",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "CF001": "配额将在约 {days_left:g} 天后耗尽（{exhaustion_date}）"
                 " — 当前 {total_latest:g} / {quota:g}，"
                 "{daily_growth:+g}/天",
        "CF002": "增长大户 — {top}",
        "CF003": "在缩小 — {metrics}：清理在生效",
        "rpt_trends": "逐指标趋势（增长快在前）",
        "col_metric": "指标",
        "col_latest": "最新",
        "col_growth": "每天",
        "col_points": "点数",
        "rpt_no_findings": "视界内无告警 — 增速装得下配额。",
        "rpt_disclaimer": "> 最近 {window} 个点的最小二乘斜率、线性外推 "
                          "— 阶跃变化会使日期失效。告警视界 90/30 天。"
                          "单位跟随你的数值（GB 或行数）。不连存储。",
        "rpt_llm_note": "容量通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(CF_I18N)
