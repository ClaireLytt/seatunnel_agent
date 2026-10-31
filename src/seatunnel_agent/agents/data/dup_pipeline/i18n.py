"""EN/ZH strings for the duplicate-pipeline reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

DP_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Duplicate Pipelines",
        "rpt_scope": "**{targets}** write target(s) over **{sources}** "
                     "source(s) · dialect `{dialect}` · ● {high} / "
                     "◐ {medium} / ○ {low}",
        "rpt_clean": "No duplicate builds — every target earns its keep.",
        "rpt_findings": "Findings",
        "col_sev": "sev",
        "col_code": "code",
        "col_tables": "tables",
        "col_issue": "issue",
        "DP001_expr": "same sources, {overlap:.0%} identical output "
                      "expressions ({detail}) — one of these is the "
                      "other, built twice",
        "DP001_input": "same source set ({detail}) — check whether one "
                       "derives from the other",
        "DP002": "reads a subset of what the second reads ({detail}) — "
                 "it may derive from that pipeline instead of "
                 "re-reading raw",
        "DP003": "`{detail}` is read directly by {n} targets — the "
                 "shared read deserves one consolidated middle layer",
        "rpt_warnings": "Parser warnings",
        "rpt_disclaimer": "> Parsed comparison of the pasted write "
                          "statements only — same inputs is evidence, "
                          "not proof; confirm business intent before "
                          "merging pipelines.",
        "rpt_llm_note": "Consolidation plan (LLM — review before acting)",
    },
    "zh": {
        "rpt_title": "重复建设检测",
        "rpt_scope": "**{targets}** 个写入目标 / **{sources}** 张源表 · "
                     "方言 `{dialect}` · ● {high} / ◐ {medium} / "
                     "○ {low}",
        "rpt_clean": "未发现重复建设 — 每个目标各有其职。",
        "rpt_findings": "发现",
        "col_sev": "级",
        "col_code": "编码",
        "col_tables": "表",
        "col_issue": "问题",
        "DP001_expr": "源表完全相同,输出表达式 {overlap:.0%} 一致"
                      "（{detail}）— 同一张表建了两遍",
        "DP001_input": "源表集合完全相同（{detail}）— 核对是否一方可由"
                       "另一方派生",
        "DP002": "读的源表是后者的子集（{detail}）— 或可改为从该链路"
                 "派生,不再重读原始表",
        "DP003": "`{detail}` 被 {n} 个目标直接读取 — 共享读取应沉淀一"
                 "层统一中间表",
        "rpt_warnings": "解析警告",
        "rpt_disclaimer": "> 仅就粘贴的写入语句做解析级对比 — 同源是"
                          "线索而非定论;合并链路前请先确认业务口径。",
        "rpt_llm_note": "收敛方案（LLM — 采纳前请复核）",
    },
}

tp = make_lookup(DP_I18N)
