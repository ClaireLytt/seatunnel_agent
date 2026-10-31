"""EN/ZH strings for the contract-generator reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

CG_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Contract Draft",
        "rpt_scope": "**{tables}** table(s), **{cols}** data column(s) "
                     "· comment coverage **{cov:.0%}** · dialect "
                     "`{dialect}`",
        "rpt_tables": "Per-table promises",
        "col_table": "table",
        "col_cols": "columns",
        "col_parts": "partitions",
        "col_comments": "comment rule",
        "col_cov": "coverage",
        "cmt_all": "require_comments",
        "cmt_keep": "keep existing",
        "cmt_none": "-",
        "rpt_yaml": "contract.yaml (paste into Contract Check)",
        "rpt_warnings": "Parser warnings",
        "rpt_disclaimer": "> Drafted from what the DDL already keeps — "
                          "tighten by hand before gating: add columns "
                          "consumers rely on, set allow_extra_columns: "
                          "false where the shape is frozen. The draft "
                          "round-trips through the Contract Check "
                          "parser.",
        "rpt_llm_note": "Tightening suggestions (LLM — review first)",
    },
    "zh": {
        "rpt_title": "契约草稿",
        "rpt_scope": "**{tables}** 张表、**{cols}** 个数据列 · 注释覆盖 "
                     "**{cov:.0%}** · 方言 `{dialect}`",
        "rpt_tables": "逐表承诺",
        "col_table": "表",
        "col_cols": "列数",
        "col_parts": "分区",
        "col_comments": "注释规则",
        "col_cov": "覆盖率",
        "cmt_all": "require_comments",
        "cmt_keep": "保留已有",
        "cmt_none": "-",
        "rpt_yaml": "contract.yaml（可直接粘到契约体检）",
        "rpt_warnings": "解析警告",
        "rpt_disclaimer": "> 草稿只承诺 DDL 当前已做到的——上闸前请人工"
                          "收紧：补上消费方依赖的列,结构冻结的表设 "
                          "allow_extra_columns: false。草稿已通过契约"
                          "体检解析器回检。",
        "rpt_llm_note": "收紧建议（LLM — 采纳前请复核）",
    },
}

tp = make_lookup(CG_I18N)
