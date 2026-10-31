"""EN/ZH strings for the alert-storm reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

AS_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Alert Storm Digest",
        "rpt_scope": "**{total}** page(s) → **{distinct}** distinct "
                     "thing(s) · dedup **{ratio}x**",
        "rpt_clusters": "Clusters (loudest first)",
        "col_count": "pages",
        "col_sources": "sources",
        "col_levels": "levels",
        "col_span": "first → last",
        "col_sample": "sample title",
        "rpt_findings": "Channel findings",
        "col_code": "code",
        "col_sev": "severity",
        "col_detail": "evidence",
        "col_rx": "prescription",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "AS002": "storm window(s) — {windows}, worst {worst_count} "
                 "page(s) in 5 min from {worst_start} (median "
                 "{median_per_bucket}/bucket)",
        "AS003": "flapping — `{signature}` fired {firings} time(s), "
                 "{window_min} min apart at its tightest",
        "AS004": "noisy source — `{source}` sent {count} "
                 "({share_pct}%) of everything",
        "rx_AS002": "a storm means ONE upstream event — route the "
                    "window's pages into one incident, then attribute "
                    "the failures (`seatunnel-agent taskfailure`)",
        "rx_AS003": "give this signature a suppression window: alert "
                    "once, re-alert on escalation only",
        "rx_AS004": "rebalance that source's thresholds — it is "
                    "training people to ignore the channel",
        "rpt_no_findings": "No storm, no flapping — the channel is "
                           "quiet enough to trust.",
        "rpt_disclaimer": "> Deterministic clustering by normalized "
                          "title signature (digits/dates/paths "
                          "stripped); storms = 5-min buckets over 3x "
                          "the median; flapping = one signature 5+ "
                          "times inside an hour. No alerting-system "
                          "connection.",
        "rpt_llm_note": "Digest note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "告警风暴摘要",
        "rpt_scope": "**{total}** 条告警 → **{distinct}** 件真实事情 · "
                     "降噪 **{ratio} 倍**",
        "rpt_clusters": "聚类（吵的在前）",
        "col_count": "条数",
        "col_sources": "来源",
        "col_levels": "级别",
        "col_span": "首条 → 末条",
        "col_sample": "标题样例",
        "rpt_findings": "通道发现",
        "col_code": "编码",
        "col_sev": "级别",
        "col_detail": "证据",
        "col_rx": "处方",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "AS002": "风暴窗口 — {windows} 个,最猛 5 分钟 {worst_count} 条"
                 "（自 {worst_start},中位数 {median_per_bucket} 条/桶）",
        "AS003": "反复横跳 — `{signature}` 发了 {firings} 次,最密时 "
                 "{window_min} 分钟内",
        "AS004": "吵闹来源 — `{source}` 发了 {count} 条"
                 "（占 {share_pct}%）",
        "rx_AS002": "风暴=同一个上游事件 — 把窗口内告警并进一个事故单,"
                    "再做失败归因（`seatunnel-agent taskfailure`）",
        "rx_AS003": "给这个签名加抑制窗口:首次告警,仅升级时再报",
        "rx_AS004": "重调该来源的阈值 — 它正在训练大家忽略整个通道",
        "rpt_no_findings": "无风暴、无横跳 — 通道足够安静,可以信。",
        "rpt_disclaimer": "> 按归一化标题签名聚类（数字/日期/路径剥离）;"
                          "风暴=5 分钟桶超中位数 3 倍;横跳=同签名一小时"
                          "内 5+ 次。不连告警系统。",
        "rpt_llm_note": "摘要通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(AS_I18N)
