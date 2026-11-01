"""EN/ZH strings for the asset-value reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

AV_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Asset Value Grading",
        "rpt_scope": "as of {today} · **{n}** asset(s) · median size "
                     "{median} GB · core {core} / common {common} / "
                     "edge {edge} / idle {idle}",
        "rpt_assets": "Grading (highest value first)",
        "col_table": "table",
        "col_score": "score",
        "col_tier": "tier",
        "col_quadrant": "quadrant",
        "col_size": "size GB",
        "col_evidence": "evidence (access/deps/recency)",
        "tier_core": "core",
        "tier_common": "common",
        "tier_edge": "edge",
        "tier_idle": "idle",
        "q_core-heavy": "high value · high cost",
        "q_core-light": "high value · low cost",
        "q_idle-heavy": "low value · high cost",
        "q_idle-light": "low value · low cost",
        "rpt_hint": "> `low value · high cost` is the storage-cost "
                    "agent's shortlist (`seatunnel-agent storagecost`); "
                    "`high value · high cost` deserves replication and "
                    "SLA review.",
        "rpt_disclaimer": "> Transparent scoring: up to 50 pts for "
                          "30-day access (log-scaled), 30 for downstream "
                          "dependencies, 20 for recency; tiers at "
                          "60/35/15. Quadrants split at the median size.",
        "rpt_llm_note": "Grading note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "数据资产价值评估",
        "rpt_scope": "截至 {today} · **{n}** 个资产 · 大小中位数 "
                     "{median} GB · 核心 {core} / 常用 {common} / "
                     "边缘 {edge} / 闲置 {idle}",
        "rpt_assets": "评级（价值高在前）",
        "col_table": "表",
        "col_score": "分数",
        "col_tier": "层级",
        "col_quadrant": "象限",
        "col_size": "大小 GB",
        "col_evidence": "证据（访问/依赖/新近）",
        "tier_core": "核心",
        "tier_common": "常用",
        "tier_edge": "边缘",
        "tier_idle": "闲置",
        "q_core-heavy": "高价值·高成本",
        "q_core-light": "高价值·低成本",
        "q_idle-heavy": "低价值·高成本",
        "q_idle-light": "低价值·低成本",
        "rpt_hint": "> 「低价值·高成本」就是存储成本治理的候选清单"
                    "（`seatunnel-agent storagecost`）；「高价值·高成本」"
                    "值得做副本与 SLA 审视。",
        "rpt_disclaimer": "> 透明打分：30 天访问最高 50 分（对数）、下游"
                          "依赖最高 30 分、新近度最高 20 分；层级阈值 "
                          "60/35/15。象限按大小中位数划分。",
        "rpt_llm_note": "评估通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(AV_I18N)
