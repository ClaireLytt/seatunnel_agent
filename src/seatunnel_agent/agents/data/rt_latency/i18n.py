"""EN/ZH strings for the realtime-latency reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

RT_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "End-to-End Latency",
        "rpt_scope": "**{events}** event(s) · dominant hop "
                     "**{dominant}**",
        "rpt_sla": " · SLA {sla_ms:g}ms breached by **{breaches}** "
                   "event(s)",
        "rpt_stages": "Per-hop latency",
        "col_hop": "hop",
        "col_count": "events",
        "col_p50": "p50 ms",
        "col_p95": "p95 ms",
        "col_max": "max ms",
        "rpt_outliers": "Outlier events (> 3x median end-to-end)",
        "col_event": "event",
        "col_e2e": "e2e ms",
        "col_worst": "worst hop",
        "rpt_no_outliers": "",
        "rpt_disclaimer": "> Deterministic percentiles over the pasted "
                          "events; hops come from consecutive *_ts "
                          "columns present per event; negative gaps "
                          "clamp to zero (clock skew). The dominant hop "
                          "is where p95 time goes — fix that stage "
                          "first.",
        "rpt_llm_note": "Latency note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "端到端延迟分析",
        "rpt_scope": "**{events}** 个事件 · 主导段 **{dominant}**",
        "rpt_sla": " · SLA {sla_ms:g}ms 破线 **{breaches}** 个事件",
        "rpt_stages": "分段延迟",
        "col_hop": "段",
        "col_count": "事件数",
        "col_p50": "p50 ms",
        "col_p95": "p95 ms",
        "col_max": "max ms",
        "rpt_outliers": "离群事件（端到端 > 3 倍中位数）",
        "col_event": "事件",
        "col_e2e": "端到端 ms",
        "col_worst": "最慢段",
        "rpt_no_outliers": "",
        "rpt_disclaimer": "> 对粘贴事件的确定性分位统计；段来自每个事件"
                          "实际存在的相邻 *_ts 列；负间隔按 0 计（时钟"
                          "漂移）。主导段就是 p95 时间花在哪 — 先修它。",
        "rpt_llm_note": "延迟通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(RT_I18N)
