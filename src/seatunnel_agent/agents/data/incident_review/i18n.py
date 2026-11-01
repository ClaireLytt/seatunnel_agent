"""EN/ZH strings for the incident-review reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

IR_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Incident Review",
        "rpt_scope": "**{events}** event(s) · MTTD **{mttd}** · MTTA "
                     "**{mtta}** · MTTR **{mttr}**",
        "na": "n/a",
        "min_suffix": " min",
        "rpt_timeline": "Timeline",
        "col_minute": "T+min",
        "col_kind": "kind",
        "col_text": "event",
        "kind_impact": "impact",
        "kind_alert": "alert",
        "kind_action": "action",
        "kind_comm": "comm",
        "kind_recovery": "recovery",
        "rpt_findings": "Findings",
        "col_sev": "sev",
        "col_code": "code",
        "col_issue": "issue",
        "IR001": "monitoring noticed {value:g} min after impact — "
                 "tighten the alert",
        "IR002": "first action came {value:g} min after the alert — "
                 "review the paging chain",
        "IR003": "a {value:g}-min silent window ({detail}) — nobody "
                 "logged anything mid-incident",
        "IR004": "no recovery event — the postmortem has no end point",
        "rpt_clean": "Detection, response and recovery all inside "
                     "bounds.",
        "rpt_disclaimer": "> Computed from the pasted log only — events "
                          "nobody wrote down never happened, as far as "
                          "this review can see. One time format per "
                          "paste (HH:MM or ISO).",
        "rpt_llm_note": "Postmortem draft (LLM — review before sharing)",
    },
    "zh": {
        "rpt_title": "事故复盘",
        "rpt_scope": "**{events}** 条事件 · 发现用时 **{mttd}** · 响应用时 "
                     "**{mtta}** · 恢复用时 **{mttr}**",
        "na": "无",
        "min_suffix": " 分",
        "rpt_timeline": "时间线",
        "col_minute": "T+分",
        "col_kind": "类型",
        "col_text": "事件",
        "kind_impact": "影响",
        "kind_alert": "告警",
        "kind_action": "处置",
        "kind_comm": "通报",
        "kind_recovery": "恢复",
        "rpt_findings": "发现",
        "col_sev": "级",
        "col_code": "编码",
        "col_issue": "问题",
        "IR001": "影响发生 {value:g} 分钟后监控才响 — 告警要收紧",
        "IR002": "告警响后 {value:g} 分钟才有第一个处置 — 复查呼叫链",
        "IR003": "{value:g} 分钟静默窗口（{detail}）— 事故中段无人记录"
                 "任何动作",
        "IR004": "没有恢复事件 — 复盘没有终点",
        "rpt_clean": "发现、响应、恢复都在界内。",
        "rpt_disclaimer": "> 只按粘贴的日志计算 — 没写下来的事件在这份"
                          "复盘里等于没发生。一次粘贴只用一种时间格式"
                          "（HH:MM 或 ISO）。",
        "rpt_llm_note": "复盘草稿（LLM — 分享前请复核）",
    },
}

tp = make_lookup(IR_I18N)
