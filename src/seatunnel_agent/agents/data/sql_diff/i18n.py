"""EN/ZH strings for the SQL-diff reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

SD_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "SQL Semantic Diff",
        "rpt_scope": "**{old}** statement(s) → **{new}** · dialect "
                     "`{dialect}` · ● {breaking} breaking / ◐ {risk} "
                     "risk / ○ {info} info",
        "rpt_identical": "No semantic difference — formatting, aliases "
                         "and ordering only.",
        "rpt_findings": "Differences",
        "col_sev": "sev",
        "col_target": "target",
        "col_what": "what",
        "col_old": "old",
        "col_new": "new",
        "kind_statement_removed": "statement removed",
        "kind_statement_added": "statement added",
        "kind_write_mode_changed": "INSERT INTO/OVERWRITE flipped",
        "kind_column_removed": "output column dropped",
        "kind_column_added": "output column added",
        "kind_column_expr_changed": "column expression changed",
        "kind_filter_changed": "filter changed",
        "kind_aggregation_changed": "aggregation changed",
        "kind_source_added": "source table joined in",
        "kind_source_removed": "source table dropped",
        "rpt_warnings": "Parser warnings",
        "rpt_disclaimer": "> Parsed comparison of the two scripts — "
                          "formatting never counts, meaning always "
                          "does. Statements pair by write target; "
                          "verify breaking rows against downstream "
                          "consumers before shipping.",
        "rpt_llm_note": "Change review (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "SQL 语义对比",
        "rpt_scope": "**{old}** 条语句 → **{new}** 条 · 方言 `{dialect}` "
                     "· ● 破坏 {breaking} / ◐ 风险 {risk} / ○ 提示 "
                     "{info}",
        "rpt_identical": "无语义差异 — 仅格式、别名或顺序变化。",
        "rpt_findings": "差异",
        "col_sev": "级",
        "col_target": "目标",
        "col_what": "变化",
        "col_old": "旧",
        "col_new": "新",
        "kind_statement_removed": "语句被删除",
        "kind_statement_added": "新增语句",
        "kind_write_mode_changed": "INSERT INTO/OVERWRITE 翻转",
        "kind_column_removed": "输出列被删",
        "kind_column_added": "新增输出列",
        "kind_column_expr_changed": "列表达式变更",
        "kind_filter_changed": "过滤条件变更",
        "kind_aggregation_changed": "聚合口径变更",
        "kind_source_added": "新接入源表",
        "kind_source_removed": "源表被移除",
        "rpt_warnings": "解析警告",
        "rpt_disclaimer": "> 两版脚本的解析级对比 — 格式从不计入,语义"
                          "全部计入。语句按写入目标配对;破坏级差异"
                          "上线前请与下游消费方核对。",
        "rpt_llm_note": "变更评审（LLM — 发送前请复核）",
    },
}

tp = make_lookup(SD_I18N)
