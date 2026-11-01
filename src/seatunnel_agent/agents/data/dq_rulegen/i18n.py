"""EN/ZH strings for the DQC-rule-draft reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

RG_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "DQC Rule Draft",
        "rpt_scope": "`{table}` · **{rows}** row(s) sampled → "
                     "**{checks}** check(s) drafted",
        "rpt_checks": "Checks",
        "col_type": "check",
        "col_target": "column(s)",
        "col_params": "threshold",
        "col_basis": "basis",
        "rpt_yaml": "rules.yaml (loads into the DQC runner as-is)",
        "rpt_skipped": "Skipped columns",
        "rpt_disclaimer": "> Drafted from what the sample already keeps "
                          "— null head-room is +5pp over the observed "
                          "rate, enums pin the observed value set, "
                          "uniqueness comes from the sample. Tighten or "
                          "loosen by hand before gating; the draft "
                          "round-trips through the rule parser.",
        "rpt_llm_note": "Tightening suggestions (LLM — review first)",
    },
    "zh": {
        "rpt_title": "质量规则草稿",
        "rpt_scope": "`{table}` · 抽样 **{rows}** 行 → 生成 **{checks}** "
                     "条检查",
        "rpt_checks": "检查项",
        "col_type": "检查",
        "col_target": "列",
        "col_params": "阈值",
        "col_basis": "依据",
        "rpt_yaml": "rules.yaml（DQC 执行器可直接加载）",
        "rpt_skipped": "跳过的列",
        "rpt_disclaimer": "> 草稿只承诺样例已做到的 — 空值率在观测值上"
                          "留 5 个百分点余量,枚举钉住观测值集,唯一性来自"
                          "抽样。上闸前请人工收放;草稿已通过规则解析器"
                          "回检。",
        "rpt_llm_note": "收紧建议（LLM — 采纳前请复核）",
    },
}

tp = make_lookup(RG_I18N)
