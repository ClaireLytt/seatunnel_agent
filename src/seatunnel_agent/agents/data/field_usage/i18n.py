"""EN/ZH strings for the field-usage reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

FU_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Field Usage",
        "rpt_scope": "**{queries}** quer(ies) over **{tables}** DDL "
                     "table(s) · ◐ {medium} / ○ {low} · {unresolved} "
                     "unresolved reference(s)",
        "rpt_tables": "Per-table usage (coldest first)",
        "col_table": "table",
        "col_reads": "reads",
        "col_star": "SELECT *",
        "col_unused": "never-referenced columns",
        "rpt_top": "Hottest columns",
        "col_column": "column",
        "col_refs": "refs",
        "rpt_findings": "Findings",
        "col_sev": "sev",
        "col_code": "code",
        "col_issue": "issue",
        "FU001": "never read by the workload — offboarding candidate",
        "FU002": "columns never referenced ({detail}) — trimming "
                 "candidates",
        "FU003": "{detail} SELECT * read(s) — column stats are blind "
                 "here",
        "rpt_clean": "Every table and column earns its reads.",
        "rpt_disclaimer": "> Counted over the pasted workload only — a "
                          "column unused today may belong to a monthly "
                          "job; check a wide-enough window before "
                          "trimming. Unqualified columns attribute only "
                          "when unambiguous, never guessed.",
        "rpt_llm_note": "Usage review (LLM — review before acting)",
    },
    "zh": {
        "rpt_title": "字段使用率盘点",
        "rpt_scope": "**{queries}** 条查询 × **{tables}** 张 DDL 表 · "
                     "◐ {medium} / ○ {low} · 未归属引用 {unresolved} 处",
        "rpt_tables": "逐表使用（最冷在前）",
        "col_table": "表",
        "col_reads": "被读次数",
        "col_star": "SELECT *",
        "col_unused": "从未被引用的列",
        "rpt_top": "最热列",
        "col_column": "列",
        "col_refs": "引用数",
        "rpt_findings": "发现",
        "col_sev": "级",
        "col_code": "编码",
        "col_issue": "问题",
        "FU001": "整个负载从未读过 — 下线候选",
        "FU002": "列从未被引用（{detail}）— 裁剪候选",
        "FU003": "{detail} 次 SELECT * — 该表列级统计失明",
        "rpt_clean": "每张表每一列都有人读。",
        "rpt_disclaimer": "> 仅统计粘贴的负载 — 今天没人读的列可能属于"
                          "月度任务,裁剪前先看足够宽的窗口。无限定列只"
                          "在无歧义时归属,从不猜测。",
        "rpt_llm_note": "使用率评审（LLM — 采纳前请复核）",
    },
}

tp = make_lookup(FU_I18N)
