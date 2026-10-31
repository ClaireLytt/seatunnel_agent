"""EN/ZH strings for the quality-trace reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

QT_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Quality Root-Cause Trace",
        "rpt_event": "event: `{table}`{col} — {symptom}",
        "rpt_event_nosym": "event: `{table}`{col}",
        "rpt_col_suffix": ".`{col}`",
        "rpt_scope": "**{n}** upstream table(s) walked (SQL lineage, "
                     "depth ≤ {depth})",
        "rpt_suspects": "Suspects (highest first)",
        "col_rank": "#",
        "col_table": "table",
        "col_dist": "hops",
        "col_score": "score",
        "col_hits": "tainted columns",
        "col_expr": "mutation points",
        "rpt_verify": "Verification SQL (top suspects)",
        "rpt_no_suspects": "The table has no upstream in the submitted "
                           "SQL — the pollution is local or the lineage "
                           "is incomplete.",
        "rpt_warnings": "Parser warnings",
        "rpt_disclaimer": "> Deterministic walk of the SQL lineage: "
                          "closer ancestors score higher, column-level "
                          "taint paths add +40, transforming expressions "
                          "+10; off-path ancestors are dampened. "
                          "Verification SQL is a template — run it on "
                          "both sides of the suspect edge.",
        "rpt_llm_note": "Trace note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "质量根因追踪",
        "rpt_event": "事件：`{table}`{col} — {symptom}",
        "rpt_event_nosym": "事件：`{table}`{col}",
        "rpt_col_suffix": ".`{col}`",
        "rpt_scope": "沿 SQL 血缘上溯 **{n}** 个上游表（深度 ≤ {depth}）",
        "rpt_suspects": "嫌疑排行（分数高在前）",
        "col_rank": "#",
        "col_table": "表",
        "col_dist": "距离",
        "col_score": "分数",
        "col_hits": "被污染列",
        "col_expr": "变换点",
        "rpt_verify": "验证 SQL（前几名嫌疑）",
        "rpt_no_suspects": "该表在提交的 SQL 里没有上游 — 污染发生在本表，"
                           "或血缘不完整。",
        "rpt_warnings": "解析警告",
        "rpt_disclaimer": "> 对 SQL 血缘的确定性上溯：距离越近分越高，"
                          "列级污染路径 +40，存在变换表达式 +10；"
                          "不在污染路径上的祖先降权。验证 SQL 是模板 — "
                          "在嫌疑边的两侧各跑一次对比。",
        "rpt_llm_note": "追踪通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(QT_I18N)
