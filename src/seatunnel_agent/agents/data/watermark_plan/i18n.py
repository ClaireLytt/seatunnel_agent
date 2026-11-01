"""EN/ZH strings for the watermark-plan reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

WM_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Watermark Plan",
        "rpt_scope": "**{events}** event(s) · out-of-order "
                     "**{ooo:.1%}** · lateness p50 **{p50:g}s** / p95 "
                     "**{p95:g}s** / p99 **{p99:g}s** / max **{max:g}s**",
        "rpt_reco": "Suggested bound: **{bound}s** (p99 + 25% margin) — "
                    "**{residual:.1%}** of events would still arrive "
                    "later",
        "rpt_snippets": "Snippets",
        "rpt_findings": "Findings",
        "col_sev": "sev",
        "col_code": "code",
        "col_issue": "issue",
        "WM001": "{value:.1%} of events arrive before their event time — "
                 "producer clock skew; fix the clocks before trusting "
                 "event time",
        "WM002": "heavy tail: max lateness is {value:g}x the regular "
                 "p99 — a bigger watermark only buys latency, route "
                 "stragglers to a side output",
        "WM003": "{value:g} straggler(s) later than one hour — excluded "
                 "from the bound, side-output material",
        "rpt_clean": "Lateness is tight — the suggested bound covers it.",
        "rpt_disclaimer": "> Measured on the pasted events only — the "
                          "bound targets the regular tail (stragglers "
                          "past one hour are excluded, or small samples "
                          "degrade p99 to max). Re-measure after "
                          "traffic-shape changes; rt_latency profiles "
                          "stage latency, this sizes event-time "
                          "disorder.",
        "rpt_llm_note": "Watermark review (LLM — review before deploy)",
    },
    "zh": {
        "rpt_title": "水位线选型",
        "rpt_scope": "**{events}** 条事件 · 乱序率 **{ooo:.1%}** · 迟到 "
                     "p50 **{p50:g}s** / p95 **{p95:g}s** / p99 "
                     "**{p99:g}s** / 最大 **{max:g}s**",
        "rpt_reco": "建议乱序容忍 **{bound} 秒**（p99 + 25% 余量）— 仍有 "
                    "**{residual:.1%}** 的事件会迟于该界",
        "rpt_snippets": "配置片段",
        "rpt_findings": "发现",
        "col_sev": "级",
        "col_code": "编码",
        "col_issue": "问题",
        "WM001": "{value:.1%} 的事件到达时间早于事件时间 — 生产端时钟漂移,"
                 "先校钟再信 event time",
        "WM002": "重尾:最大迟到是常规 p99 的 {value:g} 倍 — 加大水位线只"
                 "换来延迟,掉队者走侧输出",
        "WM003": "{value:g} 条迟到超一小时的掉队者 — 已从选型中剔除,"
                 "该进侧输出",
        "rpt_clean": "迟到分布紧凑 — 建议界足够覆盖。",
        "rpt_disclaimer": "> 只按粘贴事件测量 — 选型对准常规尾部（超一"
                          "小时的掉队者剔除,否则小样本 p99 退化成 max）。"
                          "流量形态变了要重测;rt_latency 管链路分段延迟,"
                          "本页管事件时间乱序。",
        "rpt_llm_note": "水位线评审（LLM — 部署前请复核）",
    },
}

tp = make_lookup(WM_I18N)
