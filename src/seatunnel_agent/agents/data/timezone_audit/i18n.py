"""EN/ZH strings for the timezone-audit reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

TZ_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Timezone Audit",
        "rpt_scope": "**{cols}** timestamp column(s) audited · ● {high} "
                     "/ ◐ {medium}",
        "rpt_columns": "Columns",
        "col_name": "column",
        "col_kinds": "kinds",
        "col_offsets": "offsets",
        "col_sentinel": "sentinels",
        "col_modes": "hour modes",
        "rpt_findings": "Findings",
        "col_sev": "sev",
        "col_code": "code",
        "col_issue": "issue",
        "TZ001": "explicit offsets disagree in one column ({detail}) — "
                 "direct evidence of mixed zones",
        "TZ002": "epoch units mixed ({detail}) — aggregates land off by "
                 "x1000",
        "TZ003": "bimodal hours ~8h apart ({detail}) — the UTC-vs-local "
                 "smell (heuristic, verify against the producers)",
        "TZ004": "{detail} sentinel value(s) outside 1980..2100 — "
                 "epoch-zero or overflow garbage",
        "rpt_clean": "Every timestamp column is consistent.",
        "rpt_disclaimer": "> Audited on the pasted rows only — TZ003 is "
                          "a shape heuristic for business-hours data, "
                          "not proof; TZ001/TZ002 are direct evidence. "
                          "Normalize at ingestion (one zone, one unit) "
                          "instead of patching consumers.",
        "rpt_llm_note": "Normalization note (LLM — review before acting)",
    },
    "zh": {
        "rpt_title": "时间戳体检",
        "rpt_scope": "审计 **{cols}** 个时间戳列 · ● {high} / ◐ {medium}",
        "rpt_columns": "列",
        "col_name": "列",
        "col_kinds": "形态",
        "col_offsets": "时区标记",
        "col_sentinel": "哨兵值",
        "col_modes": "小时双峰",
        "rpt_findings": "发现",
        "col_sev": "级",
        "col_code": "编码",
        "col_issue": "问题",
        "TZ001": "同列显式时区不一致（{detail}）— 混时区的直接证据",
        "TZ002": "epoch 单位混用（{detail}）— 聚合差一千倍",
        "TZ003": "小时分布双峰且相距约 8 小时（{detail}）— UTC/本地混用"
                 "嫌疑（启发式,需与生产方核实）",
        "TZ004": "{detail} 个 1980..2100 之外的哨兵值 — epoch 零点或"
                 "溢出垃圾",
        "rpt_clean": "各时间戳列口径一致。",
        "rpt_disclaimer": "> 只按粘贴的行审计 — TZ003 是面向工作时间"
                          "数据的形状启发,非定论;TZ001/TZ002 是直接"
                          "证据。在接入侧归一（一个时区、一种单位）,"
                          "别让消费方逐个打补丁。",
        "rpt_llm_note": "归一建议（LLM — 采纳前请复核）",
    },
}

tp = make_lookup(TZ_I18N)
