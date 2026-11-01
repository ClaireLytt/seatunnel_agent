"""EN/ZH strings for the data-repair reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

REPAIR_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Consistency Repair Plan",
        "rpt_scope": "table `{table}` · **{rows}** rows scanned · "
                     "**{n}** repair action(s)",
        "rpt_actions": "Actions (apply top-down; every statement is a "
                       "template — review before running)",
        "col_kind": "kind",
        "col_sev": "severity",
        "col_col": "column",
        "col_why": "why",
        "kind_dedup": "dedup",
        "kind_null_backfill": "null backfill",
        "kind_standardize": "standardize",
        "kind_numeric_cast": "numeric cast",
        "kind_format_fix": "format fix",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "why_dedup": "{layer} duplicates — {extra_rows} extra row(s)",
        "why_null": "{null_pct}% nulls",
        "why_standardize": "same value spelled differently",
        "why_numeric": "numbers stored as text, e.g. {examples}",
        "why_format": "stragglers off the dominant format (rows {rows})",
        "why_mixed": "mixed value kinds: {buckets}",
        "rpt_sql": "Repair SQL",
        "rpt_clean": "Nothing to repair — the sample came back clean.",
        "rpt_disclaimer": "> Deterministic plan from the dup-check and "
                          "sample-profile findings on the submitted rows. "
                          "<angle-bracket> placeholders need a human "
                          "decision; run everything in a staging table "
                          "first. No database connection.",
        "rpt_llm_note": "Repair note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "一致性修复方案",
        "rpt_scope": "表 `{table}` · 扫描 **{rows}** 行 · "
                     "**{n}** 条修复动作",
        "rpt_actions": "动作清单（自上而下执行；每条 SQL 都是模板 — "
                       "运行前请复核）",
        "col_kind": "类型",
        "col_sev": "级别",
        "col_col": "列",
        "col_why": "依据",
        "kind_dedup": "去重",
        "kind_null_backfill": "空值回填",
        "kind_standardize": "标准化",
        "kind_numeric_cast": "数值转换",
        "kind_format_fix": "格式修复",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "why_dedup": "{layer} 层重复 — 多余 {extra_rows} 行",
        "why_null": "空值率 {null_pct}%",
        "why_standardize": "同一个值写法不一",
        "why_numeric": "数值被存成文本，如 {examples}",
        "why_format": "偏离主格式的掉队值（行 {rows}）",
        "why_mixed": "混合类型：{buckets}",
        "rpt_sql": "修复 SQL",
        "rpt_clean": "无需修复 — 样本干净。",
        "rpt_disclaimer": "> 基于重复检测与抽样剖析发现的确定性方案；"
                          "<尖括号> 占位符需人工决策；先在 staging 表"
                          "演练再上生产。不连数据库。",
        "rpt_llm_note": "修复说明草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(REPAIR_I18N)
