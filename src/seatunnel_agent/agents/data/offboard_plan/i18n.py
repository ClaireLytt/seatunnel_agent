"""EN/ZH strings for the offboard-plan reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

OB_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Offboarding Plan",
        "rpt_scope": "`{table}` · grace **{grace}** day(s) · "
                     "**{steps}** step(s)",
        "rpt_blocked": "BLOCKED — {n} downstream consumer(s) still read "
                       "this table; migrate them first: {consumers}",
        "rpt_clear": "No downstream consumers in the pasted lineage — "
                     "clear to stage.",
        "rpt_steps": "Steps (phases run in order)",
        "col_phase": "phase",
        "col_action": "action",
        "col_state": "state",
        "col_detail": "detail",
        "phase_announce": "announce",
        "phase_freeze": "freeze",
        "phase_archive": "archive",
        "phase_drop": "drop",
        "act_migrate_consumers": "migrate the consumers off first",
        "act_notify": "announce the retirement deadline",
        "act_mark_deprecated": "mark deprecated (reads keep working)",
        "act_stop_producer": "pause the producing job",
        "act_snapshot": "snapshot to the archive table",
        "act_verify_snapshot": "verify the snapshot row count",
        "act_drop_table": "drop (commented until verified)",
        "state_safe": "ready",
        "state_unsafe": "review",
        "rpt_sql": "Templates",
        "rpt_warnings": "Parser warnings",
        "rpt_disclaimer": "> Staged from the pasted lineage only — "
                          "consumers outside this SQL (BI dashboards, "
                          "ad-hoc users) are invisible here; pair with a "
                          "Field Usage window before the drop. The DROP "
                          "stays commented until the archive is "
                          "verified.",
        "rpt_llm_note": "Retirement notice (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "下线方案",
        "rpt_scope": "`{table}` · 公示期 **{grace}** 天 · 共 **{steps}** 步",
        "rpt_blocked": "受阻 — 仍有 {n} 个下游在读该表,先迁移: {consumers}",
        "rpt_clear": "粘贴血缘内无下游消费方 — 可进入分阶段下线。",
        "rpt_steps": "步骤（阶段按序执行）",
        "col_phase": "阶段",
        "col_action": "动作",
        "col_state": "状态",
        "col_detail": "说明",
        "phase_announce": "公示",
        "phase_freeze": "冻结",
        "phase_archive": "归档",
        "phase_drop": "删除",
        "act_migrate_consumers": "先迁移下游消费方",
        "act_notify": "公示下线时限",
        "act_mark_deprecated": "标记 deprecated（读仍可用）",
        "act_stop_producer": "暂停产出任务",
        "act_snapshot": "快照到归档表",
        "act_verify_snapshot": "核对归档行数",
        "act_drop_table": "删表（核验前保持注释）",
        "state_safe": "可执行",
        "state_unsafe": "待评审",
        "rpt_sql": "模板",
        "rpt_warnings": "解析警告",
        "rpt_disclaimer": "> 仅按粘贴血缘分阶段 — 血缘外的消费方（BI 看板/"
                          "即席查询）在此不可见,删除前配合字段使用率拉一"
                          "个足够宽的窗口。DROP 在归档核验前保持注释。",
        "rpt_llm_note": "下线通告（LLM — 发送前请复核）",
    },
}

tp = make_lookup(OB_I18N)
