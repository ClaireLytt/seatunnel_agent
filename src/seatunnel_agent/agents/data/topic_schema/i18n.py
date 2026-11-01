"""EN/ZH strings for the topic-schema-diff reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

TS_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Topic Schema Diff",
        "rpt_scope": "{flavor} · mode **{mode}** · **{old}** → **{new}** "
                     "field(s) · verdict: **{verdict}**",
        "verdict_ok": "COMPATIBLE",
        "verdict_bad": "INCOMPATIBLE",
        "rpt_findings": "Changes",
        "col_sev": "sev",
        "col_kind": "change",
        "col_field": "field",
        "col_old": "old",
        "col_new": "new",
        "col_breaks": "breaks",
        "kind_field_added": "field added",
        "kind_field_removed": "field removed",
        "kind_type_changed": "type changed",
        "kind_requirement_changed": "optional → required",
        "rpt_clean": "The schemas match — nothing to migrate.",
        "rpt_disclaimer": "> Judged by the registry's rules — BACKWARD: "
                          "the new schema must read old data (adding a "
                          "field without a default breaks it); FORWARD: "
                          "old readers must survive new data (removing "
                          "a defaultless field breaks it); types pass "
                          "only along Avro promotions or a union "
                          "widening by null. Breaking rows block the "
                          "registry; fix them before publishing.",
        "rpt_llm_note": "Rollout note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "消息 Schema 对比",
        "rpt_scope": "{flavor} · 兼容模式 **{mode}** · 字段 **{old}** → "
                     "**{new}** · 结论: **{verdict}**",
        "verdict_ok": "兼容",
        "verdict_bad": "不兼容",
        "rpt_findings": "变更",
        "col_sev": "级",
        "col_kind": "变更",
        "col_field": "字段",
        "col_old": "旧",
        "col_new": "新",
        "col_breaks": "破坏模式",
        "kind_field_added": "新增字段",
        "kind_field_removed": "删除字段",
        "kind_type_changed": "改类型",
        "kind_requirement_changed": "可选 → 必填",
        "rpt_clean": "两版 Schema 一致 — 无需迁移。",
        "rpt_disclaimer": "> 按注册中心规则判定 — BACKWARD:新 Schema 要能"
                          "读旧数据（新增无默认值字段即破坏）;FORWARD:旧"
                          "读者要扛住新数据（删除无默认值字段即破坏）;"
                          "类型只认 Avro 升格链或 union 加 null 的拓宽。"
                          "breaking 行会被注册中心拒绝,发布前先修。",
        "rpt_llm_note": "发布通报（LLM — 发送前请复核）",
    },
}

tp = make_lookup(TS_I18N)
