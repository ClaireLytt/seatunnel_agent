"""EN/ZH strings for the mask-preview reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

MP_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Mask Preview",
        "rpt_scope": "**{rows}** row(s), **{cols}** column(s) · "
                     "**{sensitive}** sensitive column(s) masked",
        "rpt_clean": "No sensitive columns detected — the sample ships "
                     "as-is.",
        "rpt_columns": "Masking rules",
        "col_sev": "sev",
        "col_name": "column",
        "col_category": "category",
        "col_by": "detected by",
        "col_before": "before",
        "col_after": "after",
        "by_name": "name",
        "by_value": "values",
        "by_name+value": "name + values",
        "rpt_preview": "Masked rows (first {n})",
        "rpt_disclaimer": "> Format-preserving value masks over the "
                          "pasted sample only — names match the "
                          "pii_scan catalog, values match CN "
                          "phone/ID/email/bank shapes. Nothing leaves "
                          "the process; review the rules before "
                          "shipping masked data anywhere.",
        "rpt_llm_note": "Masking policy note (LLM — review first)",
    },
    "zh": {
        "rpt_title": "脱敏预览",
        "rpt_scope": "**{rows}** 行 × **{cols}** 列 · 命中敏感列 "
                     "**{sensitive}** 个并已脱敏",
        "rpt_clean": "未检出敏感列 — 样例可直接使用。",
        "rpt_columns": "脱敏规则",
        "col_sev": "级",
        "col_name": "列",
        "col_category": "类别",
        "col_by": "判定依据",
        "col_before": "脱敏前",
        "col_after": "脱敏后",
        "by_name": "列名",
        "by_value": "值形态",
        "by_name+value": "列名+值形态",
        "rpt_preview": "脱敏后样例（前 {n} 行）",
        "rpt_disclaimer": "> 仅对粘贴样例做保格式值级脱敏 — 列名对"
                          "pii_scan 规则库,值形态对手机号/身份证/邮箱/"
                          "银行卡。数据不出进程;脱敏结果外发前请人工"
                          "复核规则。",
        "rpt_llm_note": "脱敏策略说明（LLM — 采纳前请复核）",
    },
}

tp = make_lookup(MP_I18N)
