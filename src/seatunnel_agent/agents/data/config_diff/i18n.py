"""EN/ZH strings for the config-diff reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

CDF_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Config Drift",
        "rpt_scope": "left **{left}** key(s) vs right **{right}** · "
                     "**{n}** difference(s)",
        "rpt_entries": "Differences (riskiest first)",
        "col_sev": "severity",
        "col_kind": "kind",
        "col_key": "key",
        "col_old": "left",
        "col_new": "right",
        "kind_changed": "changed",
        "kind_added": "added",
        "kind_removed": "removed",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "rpt_identical": "The two configs are semantically identical — "
                         "comments, ordering and formatting aside.",
        "rpt_disclaimer": "> Semantic comparison through the HOCON "
                          "parser (SeaTunnel conf, JSON and flat "
                          "properties all parse); secret-shaped values "
                          "are masked but their changes still count. "
                          "High = throughput/state/destination keys, "
                          "mid = tuning knobs.",
        "rpt_llm_note": "Drift note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "配置漂移对比",
        "rpt_scope": "左 **{left}** 个键 vs 右 **{right}** · 差异 "
                     "**{n}** 处",
        "rpt_entries": "差异（风险高在前）",
        "col_sev": "级别",
        "col_kind": "类型",
        "col_key": "键",
        "col_old": "左",
        "col_new": "右",
        "kind_changed": "改值",
        "kind_added": "新增",
        "kind_removed": "删除",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "rpt_identical": "两份配置语义相同 — 注释、顺序与格式不计。",
        "rpt_disclaimer": "> 经 HOCON 解析器做语义对比（SeaTunnel conf/"
                          "JSON/扁平 properties 均可解析）；密钥形值已"
                          "脱敏但改动仍计。高=吞吐/状态/数据去向类键,"
                          "中=调优旋钮。",
        "rpt_llm_note": "漂移通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(CDF_I18N)
