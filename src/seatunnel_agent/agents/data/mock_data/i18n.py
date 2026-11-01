"""EN/ZH strings for the mock-data reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

MK_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Mock Data",
        "rpt_scope": "**{count}** row(s) generated from a **{sample}**-row "
                     "sample · seed **{seed}** · sensitive columns "
                     "synthesized, never sampled",
        "rpt_plans": "Column strategies",
        "col_name": "column",
        "col_strategy": "strategy",
        "col_detail": "parameters",
        "st_sequence": "sequence",
        "st_int_range": "integer in range",
        "st_float_range": "decimal in range",
        "st_date_range": "date in window",
        "st_enum": "draw from observed values",
        "st_text": "random text, sampled length",
        "st_null": "always null",
        "st_fake": "synthesized {category} (never a real value)",
        "rpt_preview": "Generated rows (first {n})",
        "rpt_disclaimer": "> Shape-preserving synthesis from the pasted "
                          "sample — ranges, formats, value "
                          "distributions and null rates carry over; "
                          "sensitive columns are generated fresh and "
                          "never copied. Same sample + seed = same "
                          "rows. Grab the full CSV from the JSON "
                          "payload.",
        "rpt_llm_note": "Dataset note (LLM — review first)",
    },
    "zh": {
        "rpt_title": "测试数据生成",
        "rpt_scope": "由 **{sample}** 行样例生成 **{count}** 行 · 种子 "
                     "**{seed}** · 敏感列全部合成,绝不取样",
        "rpt_plans": "逐列策略",
        "col_name": "列",
        "col_strategy": "策略",
        "col_detail": "参数",
        "st_sequence": "自增序列",
        "st_int_range": "区间内整数",
        "st_float_range": "区间内小数",
        "st_date_range": "窗口内日期",
        "st_enum": "按观测值分布抽取",
        "st_text": "随机文本,长度取样",
        "st_null": "恒为空",
        "st_fake": "合成{category}（绝非真实值）",
        "rpt_preview": "生成样例（前 {n} 行）",
        "rpt_disclaimer": "> 按粘贴样例保形合成 — 数值区间、日期窗口、"
                          "值分布与空值率全部保留;敏感列现场合成,绝不"
                          "复制样例值。同样例同种子必得同结果。完整 "
                          "CSV 在 JSON 载荷里。",
        "rpt_llm_note": "数据集说明（LLM — 采纳前请复核）",
    },
}

tp = make_lookup(MK_I18N)
