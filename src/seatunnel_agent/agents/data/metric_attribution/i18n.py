"""EN/ZH strings for the metric-attribution reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

MA_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Metric Change Attribution",
        "rpt_scope": "`{metric}`: **{base:g}** → **{cur:g}** "
                     "(**{delta:+g}**{pct})",
        "rpt_pct": ", {p:+g}%",
        "rpt_findings": "Findings",
        "col_code": "code",
        "col_sev": "severity",
        "col_detail": "evidence",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "dir_drop": "drop",
        "dir_rise": "rise",
        "MA001": "top contributor on `{dimension}` — `{value}` moved "
                 "{contribution:+g} ({share_pct}% of the {direction})",
        "MA002": "concentrated — `{dimension}`=`{value}` alone carries "
                 "{share_pct}% of the move: a single-value incident, "
                 "not a trend",
        "MA003": "mix shift on `{dimension}` — ups {ups:+g} and downs "
                 "-{downs:g} largely cancel into {net:+g}: the total "
                 "hides opposite moves",
        "rpt_dim": "Breakdown by `{dim}` (largest movers first)",
        "col_value": "value",
        "col_base": "baseline",
        "col_cur": "current",
        "col_contrib": "contribution",
        "col_share": "share of Δ",
        "col_status": "status",
        "status_moved": "moved",
        "status_appeared": "appeared",
        "status_vanished": "vanished",
        "rpt_flat": "The totals match — nothing to attribute.",
        "rpt_disclaimer": "> Exact additive decomposition: per "
                          "dimension, the per-value contributions sum "
                          "to the total change. Next step for the top "
                          "contributor: trace it upstream "
                          "(`seatunnel-agent qualitytrace`).",
        "rpt_llm_note": "Attribution note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "指标异动归因",
        "rpt_scope": "`{metric}`：**{base:g}** → **{cur:g}**"
                     "（**{delta:+g}**{pct}）",
        "rpt_pct": "，{p:+g}%",
        "rpt_findings": "发现",
        "col_code": "编码",
        "col_sev": "级别",
        "col_detail": "证据",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "dir_drop": "跌幅",
        "dir_rise": "涨幅",
        "MA001": "`{dimension}` 维度头号贡献 — `{value}` 变动 "
                 "{contribution:+g}（占整体{direction}的 {share_pct}%）",
        "MA002": "高度集中 — `{dimension}`=`{value}` 一个值扛了 "
                 "{share_pct}% 的变动：单点事故，不是趋势",
        "MA003": "`{dimension}` 维度结构漂移 — 涨 {ups:+g} 跌 "
                 "-{downs:g} 大幅对冲后净 {net:+g}：总量掩盖了反向变动",
        "rpt_dim": "按 `{dim}` 分解（变动大在前）",
        "col_value": "取值",
        "col_base": "基线",
        "col_cur": "当前",
        "col_contrib": "贡献额",
        "col_share": "占 Δ 比",
        "col_status": "状态",
        "status_moved": "变动",
        "status_appeared": "新出现",
        "status_vanished": "消失",
        "rpt_flat": "总量一致 — 无需归因。",
        "rpt_disclaimer": "> 精确可加分解：每个维度下各取值贡献额之和"
                          "等于总变动。头号贡献的下一步：沿血缘上溯"
                          "（`seatunnel-agent qualitytrace`）。",
        "rpt_llm_note": "归因通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(MA_I18N)
