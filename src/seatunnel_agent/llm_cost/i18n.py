# -*- coding: utf-8 -*-
"""EN/ZH strings for LLM cost reports and the /llmcost page."""

from __future__ import annotations

COST_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "LLM Cost",
        "rpt_total": ("Last {days} days: {calls} calls · {cost} · "
                      "{inp:,} in / {out:,} out tokens"),
        "rpt_empty": "No LLM calls recorded in this window.",
        "rpt_model_header": "Model | Calls | Input | Output | Cost",
        "rpt_agent_header": "Agent | Calls | Cost",
        "rpt_unpriced_cell": "unpriced",
        "rpt_anomaly_title": "⚠️ Cost anomalies",
        "rpt_anomaly_item": ("- **{day}**: {cost} — more than 2× the "
                             "trailing-7-day mean ({baseline})"),
        "rpt_unpriced_warn": ("> ⚠️ No price on file for {models} — their "
                              "spend is **not** included. Add them to "
                              "`~/.seatunnel-agent/pricing.yaml`."),
        "rpt_disclaimer": ("> Costs are estimates from an approximate, "
                           "overridable price catalog — not a bill."),
    },
    "zh": {
        "rpt_title": "LLM 成本",
        "rpt_total": ("近 {days} 天:{calls} 次调用 · {cost} · "
                      "输入 {inp:,} / 输出 {out:,} tokens"),
        "rpt_empty": "该时间窗内没有 LLM 调用记录。",
        "rpt_model_header": "模型 | 调用 | 输入 | 输出 | 成本",
        "rpt_agent_header": "Agent | 调用 | 成本",
        "rpt_unpriced_cell": "无价格",
        "rpt_anomaly_title": "⚠️ 成本异常",
        "rpt_anomaly_item": ("- **{day}**:{cost} — 超过前 7 天均值"
                             "({baseline})的 2 倍"),
        "rpt_unpriced_warn": ("> ⚠️ 以下模型没有价格记录:{models} — 其消耗"
                              "**未计入**成本。可在 "
                              "`~/.seatunnel-agent/pricing.yaml` 中补充。"),
        "rpt_disclaimer": ("> 成本为基于近似价格表的估算(可用 YAML 覆盖),"
                           "不是账单。"),
    },
}


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


def tp(lang: str, key: str) -> str:
    lang = normalize_lang(lang)
    return COST_I18N.get(lang, {}).get(key) or COST_I18N["zh"].get(key, key)
