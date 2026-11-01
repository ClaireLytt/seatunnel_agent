"""EN/ZH strings for the DDL-evolve reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

DE_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "DDL Migration",
        "rpt_scope": "**{total}** step(s) · **{safe}** ready to run, "
                     "**{unsafe}** commented for review · dialect "
                     "`{dialect}`",
        "rpt_identical": "The snapshots match — nothing to migrate.",
        "rpt_steps": "Steps",
        "col_state": "state",
        "col_kind": "change",
        "col_table": "table",
        "col_note": "review note",
        "state_safe": "ready",
        "state_unsafe": "review",
        "kind_table_added": "new table",
        "kind_table_removed": "drop table",
        "kind_column_added": "add column",
        "kind_column_removed": "drop column",
        "kind_type_changed": "type change",
        "kind_column_renamed": "rename column",
        "kind_comment_changed": "comment update",
        "kind_partition_changed": "partition layout",
        "rpt_script": "Migration script",
        "rpt_warnings": "Parser warnings",
        "rpt_disclaimer": "> Generated from the two snapshots "
                          "(schema_drift's diff): widenings, additions, "
                          "renames and comments run as-is; drops, "
                          "narrowings and partition changes stay "
                          "commented until a human decides. Rehearse on "
                          "staging first.",
        "rpt_llm_note": "Migration review (LLM — review before running)",
    },
    "zh": {
        "rpt_title": "DDL 迁移脚本",
        "rpt_scope": "共 **{total}** 步 · **{safe}** 步可直接执行,"
                     "**{unsafe}** 步已注释待人工定夺 · 方言 `{dialect}`",
        "rpt_identical": "两个快照一致 — 无需迁移。",
        "rpt_steps": "步骤",
        "col_state": "状态",
        "col_kind": "变更",
        "col_table": "表",
        "col_note": "评审提示",
        "state_safe": "可执行",
        "state_unsafe": "待评审",
        "kind_table_added": "新建表",
        "kind_table_removed": "删表",
        "kind_column_added": "加列",
        "kind_column_removed": "删列",
        "kind_type_changed": "改类型",
        "kind_column_renamed": "改列名",
        "kind_comment_changed": "改注释",
        "kind_partition_changed": "分区布局",
        "rpt_script": "迁移脚本",
        "rpt_warnings": "解析警告",
        "rpt_disclaimer": "> 由两个快照生成（复用 schema_drift 差异）:"
                          "拓宽/加列/改名/改注释可直接执行;删表删列、"
                          "类型收窄、分区变更保持注释,人工定夺后再放行。"
                          "先在 staging 演练。",
        "rpt_llm_note": "迁移评审（LLM — 执行前请复核）",
    },
}

tp = make_lookup(DE_I18N)
