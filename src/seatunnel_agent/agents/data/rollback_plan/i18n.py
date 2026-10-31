"""EN/ZH strings for the rollback-plan reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

RB_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Rollback Plan",
        "rpt_scope": "bad load on `{table}` ({parts}) · restore mode "
                     "**{mode}** · **{levels}** downstream level(s), "
                     "{touched} table(s) touched{est}",
        "rpt_est": " · critical path ~**{m:g} min**",
        "rpt_steps": "Steps (levels run in order; tables inside one "
                     "level run in parallel)",
        "col_level": "level",
        "col_action": "action",
        "col_table": "table",
        "action_restore": "restore",
        "action_rerun": "re-run",
        "action_verify": "verify",
        "rpt_sql": "Templates",
        "rpt_warnings": "Parser warnings",
        "rpt_disclaimer": "> Deterministic walk of the SQL lineage "
                          "DOWNSTREAM of the bad table; templates need "
                          "the <placeholders> decided before running. "
                          "Rehearse on staging; verify counts against a "
                          "known-good day.",
        "rpt_llm_note": "Rollback note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "回滚编排",
        "rpt_scope": "`{table}` 写坏（{parts}）· 恢复方式 **{mode}** · "
                     "下游 **{levels}** 层,共涉及 {touched} 张表{est}",
        "rpt_est": " · 关键路径约 **{m:g} 分钟**",
        "rpt_steps": "步骤（层间按序,层内可并行）",
        "col_level": "层",
        "col_action": "动作",
        "col_table": "表",
        "action_restore": "恢复",
        "action_rerun": "重跑",
        "action_verify": "验证",
        "rpt_sql": "模板",
        "rpt_warnings": "解析警告",
        "rpt_disclaimer": "> 沿 SQL 血缘向下游的确定性编排;模板里的"
                          "<占位符>需先决策再执行。先在 staging 演练;"
                          "验证计数对照一个已知正常日。",
        "rpt_llm_note": "回滚通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(RB_I18N)
