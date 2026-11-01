"""EN/ZH strings for the model-review reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

MR_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Model Review",
        "rpt_scope": "**{tables}** table(s) ({roles}) · dialect "
                     "`{dialect}` · ● {high} / ◐ {medium} / ○ {low}",
        "rpt_clean": "The star schema holds — no findings.",
        "rpt_findings": "Findings",
        "col_sev": "sev",
        "col_code": "code",
        "col_table": "table",
        "col_issue": "issue",
        "MR001": "dimension has no primary-key column (id / *_id) — "
                 "facts cannot join it",
        "MR002": "fact table has no partitions — unprunable scans at "
                 "fact volume",
        "MR003": "descriptive attributes live in a fact ({detail}) — "
                 "push them to a dimension",
        "MR004": "attribute `{detail}` is copied across facts — copies "
                 "drift apart; keep it in one dimension",
        "MR005": "aggregate table has no measure-shaped numeric column",
        "MR006": "table is {detail} columns wide — split by subject",
        "MR007": "fact table has no *_id column — it reaches no "
                 "dimension",
        "role_dim": "dim",
        "role_fact": "fact",
        "role_raw": "raw",
        "role_other": "other",
        "rpt_warnings": "Parser warnings",
        "rpt_disclaimer": "> Shape review of the pasted DDL only — "
                          "prefixes (dim/dwd/dws/ods) decide each "
                          "table's role; tables outside those layers "
                          "only get the width check. No data is read.",
        "rpt_llm_note": "Modeling review (LLM — review before acting)",
    },
    "zh": {
        "rpt_title": "建模体检",
        "rpt_scope": "**{tables}** 张表（{roles}）· 方言 `{dialect}` · "
                     "● {high} / ◐ {medium} / ○ {low}",
        "rpt_clean": "星型结构成立 — 无发现。",
        "rpt_findings": "发现",
        "col_sev": "级",
        "col_code": "编码",
        "col_table": "表",
        "col_issue": "问题",
        "MR001": "维表没有主键列（id / *_id）— 事实表无从关联",
        "MR002": "事实表未分区 — 事实量级下扫描无法裁剪",
        "MR003": "描述性维度属性混在事实表里（{detail}）— 应下沉维表",
        "MR004": "属性 `{detail}` 在多张事实表间复制 — 副本会漂移,应收敛"
                 "到一张维表",
        "MR005": "汇总表没有度量形数值列",
        "MR006": "表宽 {detail} 列 — 建议按主题拆分",
        "MR007": "事实表没有任何 *_id 列 — 关联不到任何维表",
        "role_dim": "维表",
        "role_fact": "事实",
        "role_raw": "原始",
        "role_other": "其他",
        "rpt_warnings": "解析警告",
        "rpt_disclaimer": "> 仅就粘贴的 DDL 做结构体检 — 前缀"
                          "（dim/dwd/dws/ods）决定表角色;层外的表只做"
                          "宽表检查。不读任何数据。",
        "rpt_llm_note": "建模评审（LLM — 采纳前请复核）",
    },
}

tp = make_lookup(MR_I18N)
