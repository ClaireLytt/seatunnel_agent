"""EN/ZH strings for the data-dictionary reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

DD_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Data Dictionary",
        "rpt_scope": "**{tables}** table(s) · average comment coverage "
                     "**{coverage}%**",
        "rpt_table": "`{table}` — {comment} (comment coverage "
                     "{coverage}%)",
        "rpt_table_nocmt": "`{table}` (comment coverage {coverage}%)",
        "col_name": "column",
        "col_role": "role",
        "col_comment": "comment",
        "col_usage": "usage (filter/join/group)",
        "role_key": "key",
        "role_time": "time",
        "role_measure": "measure",
        "role_flag": "flag",
        "role_dimension": "dimension",
        "rpt_disclaimer": "> Deterministic skeleton: roles from name "
                          "shapes, usage mined from the submitted SQL "
                          "workload. Empty comments are the gap list for "
                          "the LLM draft or the owners.",
        "rpt_llm_note": "Business descriptions (LLM draft — review "
                        "before publishing)",
    },
    "zh": {
        "rpt_title": "数据字典",
        "rpt_scope": "**{tables}** 张表 · 平均注释覆盖率 **{coverage}%**",
        "rpt_table": "`{table}` — {comment}（注释覆盖率 {coverage}%）",
        "rpt_table_nocmt": "`{table}`（注释覆盖率 {coverage}%）",
        "col_name": "列",
        "col_role": "角色",
        "col_comment": "注释",
        "col_usage": "使用（过滤/关联/分组）",
        "role_key": "键",
        "role_time": "时间",
        "role_measure": "度量",
        "role_flag": "标志",
        "role_dimension": "维度",
        "rpt_disclaimer": "> 确定性骨架：角色由命名形态推断，使用频次来自"
                          "提交的 SQL 负载。空注释就是待补清单 — 交给 "
                          "LLM 草拟或负责人补全。",
        "rpt_llm_note": "业务描述（LLM 草稿 — 发布前请复核）",
    },
}

tp = make_lookup(DD_I18N)
