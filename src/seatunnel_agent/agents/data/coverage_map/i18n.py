"""EN/ZH strings for the coverage-map reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

CM_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Coverage Map",
        "rpt_scope": "**{covered}/{total}** table(s) protected "
                     "(**{share:.0%}**) · ● {high} / ◐ {medium}",
        "rpt_tables": "Per-table protection (unprotected first)",
        "col_table": "table",
        "col_rowcount": "row_count",
        "col_nullrate": "null_rate",
        "col_unique": "unique",
        "col_enum": "enum",
        "col_contract": "contract",
        "yes": "yes",
        "rpt_findings": "Findings",
        "col_sev": "sev",
        "col_code": "code",
        "col_issue": "issue",
        "CM001": "no DQC check and no contract — this table ships "
                 "unguarded",
        "CM002": "the {detail} artifact names a table absent from the "
                 "DDL — a dead gate guarding nothing",
        "rpt_clean": "Every table carries at least one gate.",
        "rpt_disclaimer": "> Mapped from the pasted artifacts only — "
                          "gates configured elsewhere are invisible "
                          "here. Fix the hot-layer (dwd/dws/ads) holes "
                          "first: that is where consumers feel the "
                          "breakage. dq_rulegen and contract_gen draft "
                          "the missing gates.",
        "rpt_llm_note": "Coverage review (LLM — review before planning)",
    },
    "zh": {
        "rpt_title": "质量覆盖地图",
        "rpt_scope": "**{covered}/{total}** 张表有防护（**{share:.0%}**）"
                     "· ● {high} / ◐ {medium}",
        "rpt_tables": "逐表防护（裸奔在前）",
        "col_table": "表",
        "col_rowcount": "row_count",
        "col_nullrate": "null_rate",
        "col_unique": "unique",
        "col_enum": "enum",
        "col_contract": "契约",
        "yes": "有",
        "rpt_findings": "发现",
        "col_sev": "级",
        "col_code": "编码",
        "col_issue": "问题",
        "CM001": "既无 DQC 检查也无契约 — 这张表在裸奔",
        "CM002": "{detail} 工件声明的表不在 DDL 里 — 守着空城的死闸",
        "rpt_clean": "每张表至少有一道闸。",
        "rpt_disclaimer": "> 只按粘贴的工件作图 — 配在别处的闸在这里"
                          "不可见。先补热层（dwd/dws/ads）的洞:那是消费"
                          "方直接挨刀的地方。缺的闸用 dq_rulegen 和 "
                          "contract_gen 一键起草。",
        "rpt_llm_note": "覆盖评审（LLM — 排计划前请复核）",
    },
}

tp = make_lookup(CM_I18N)
