# -*- coding: utf-8 -*-
"""EN/ZH strings for the SQL Review page and CR report rendering.

Mirrors the ``data_comparison.i18n`` pattern: one flat dict per language,
looked up via ``sr(lang, key)`` with Chinese as the fallback (the source
language of the linter findings).
"""

from __future__ import annotations

# English labels for report.CHECK_CATALOG (keys must stay in sync).
CHECK_CATALOG_EN: dict[str, str] = {
    "join_condition": "JOIN condition & key accuracy",
    "join_cartesian": "JOIN type consistency / many-to-many & cartesian product",
    "where_syntax": "WHERE syntax & NULL comparison",
    "where_partition": "Time range & partition predicate style",
    "groupby_completeness": "GROUP BY completeness",
    "aggregate_functions": "Aggregate function correctness",
    "calculation": "Calculation logic (NULL / div-zero / money precision / ratio)",
    "null_handling": "NULL handling (COALESCE / NVL / empty string)",
    "dedup": "Deduplication & primary-key uniqueness",
    "type_cast": "Type conversion & comparison",
    "partition_pruning": "Partition pruning & granularity",
    "data_skew": "Data skew (hot keys / large-table JOIN)",
    "resource_usage": "Resource usage (full scan / temp tables / incremental)",
    "readability": "Code style & readability",
    "time_boundary": "Time boundary logic (cross-day / timezone / month-end / leap year)",
}

SR_I18N: dict[str, dict[str, str]] = {
    "en": {
        # --- UI chrome ---
        "sr_title": "## 🔍 SQL Code Review",
        "sr_subtitle": (
            "Static rules + LLM semantic review. Supports Hive / Spark / "
            "Flink / MaxCompute. Pure static analysis — the SQL is never executed."
        ),
        "sr_sql_placeholder": "Paste the SQL to review…",
        "sr_dialect": "SQL Dialect",
        "sr_mode": "Review Mode",
        "sr_mode_static": "Static review (fast, no LLM)",
        "sr_mode_llm": "LLM deep review",
        "sr_ddl_accordion": "Table DDL (optional, for schema checks)",
        "sr_ddl_label": "CREATE TABLE statements",
        "sr_review_btn": "Start Review",
        "sr_fix_btn": "Generate Fixed SQL (LLM)",
        "sr_report_placeholder": "*The review report will appear here*",
        "sr_fixed_sql": "Fixed SQL",
        "sr_stats_accordion": "📈 Review History Stats",
        "sr_stats_placeholder": "*Click refresh to load*",
        "sr_refresh": "Refresh Stats",
        # --- UI dynamic messages ---
        "sr_input_sql_first": "Please enter SQL first.",
        "sr_review_failed": "❌ **Review failed**",
        "sr_fix_need_review": "-- Run a review first",
        "sr_fix_failed": "-- Fix failed",
        "sr_no_records": "No review records yet.",
        "sr_stat_reviews": "Reviews",
        "sr_stat_findings": "Total findings",
        "sr_sev_critical": "🔴 Critical",
        "sr_sev_risk": "🟡 Risk",
        "sr_sev_suggestion": "🟢 Suggestion",
        "sr_top_categories": "**Top issue categories**",
        # --- CR report ---
        "sr_report_title": "## CR Report",
        "sr_sec_critical": "### 🔴 Critical Issues (must fix)",
        "sr_sec_risk": "### 🟡 Potential Risks (should fix)",
        "sr_sec_suggestion": "### 🟢 Suggestions (optional)",
        "sr_none": "None",
        "sr_h_no": "No.",
        "sr_h_desc": "Description",
        "sr_h_loc": "Location",
        "sr_h_impact": "Impact",
        "sr_h_risk": "Risk",
        "sr_h_fix": "Fix",
        "sr_h_opt": "Suggestion",
        "sr_sec_lineage": "### 🔗 Table Lineage",
        "sr_lin_sources": "Source tables",
        "sr_lin_targets": "Target tables",
        "sr_lin_none_target": "None (query only)",
        "sr_lin_columns": "Column lineage:",
        "sr_lin_agg": " (aggregated)",
        "sr_sec_stats": "### 📊 Check Statistics",
        "sr_stats_total": "Total checks",
        "sr_stats_passed": "Passed",
        "sr_stats_problems": "Problems",
        "sr_stats_risks": "Risks",
        "sr_sec_verdict": "### 💡 Overall Verdict",
        "sr_sum_critical": (
            "The code has {n} critical issue(s) that would break execution "
            "or produce wrong results; they must be fixed before release."
        ),
        "sr_sum_risk": (
            "No critical issues, but {n} potential risk(s) remain; fix them "
            "as suggested before release."
        ),
        "sr_sum_pass": "Checks passed — no obvious issues found.",
        # --- agent / fixer ---
        "sr_no_sql": "No SQL to review.",
        "sr_fix_no_sql": "The model returned no usable fixed SQL",
    },
    "zh": {
        # --- UI chrome ---
        "sr_title": "## 🔍 SQL 代码审查",
        "sr_subtitle": (
            "静态规则 + LLM 语义审查，支持 Hive / Spark / Flink / MaxCompute。"
            "纯静态分析，不执行 SQL。"
        ),
        "sr_sql_placeholder": "粘贴要审查的 SQL……",
        "sr_dialect": "SQL 方言",
        "sr_mode": "审查模式",
        "sr_mode_static": "静态审查（快速，无需 LLM）",
        "sr_mode_llm": "LLM 深度审查",
        "sr_ddl_accordion": "表结构 DDL（可选，用于 schema 校验）",
        "sr_ddl_label": "CREATE TABLE 语句",
        "sr_review_btn": "开始审查",
        "sr_fix_btn": "生成修复 SQL（LLM）",
        "sr_report_placeholder": "*审查报告将显示在这里*",
        "sr_fixed_sql": "修复后 SQL",
        "sr_stats_accordion": "📈 审查历史统计",
        "sr_stats_placeholder": "*点击刷新查看*",
        "sr_refresh": "刷新统计",
        # --- UI dynamic messages ---
        "sr_input_sql_first": "请先输入 SQL。",
        "sr_review_failed": "❌ **审查失败**",
        "sr_fix_need_review": "-- 请先完成一次审查",
        "sr_fix_failed": "-- 修复失败",
        "sr_no_records": "暂无审查记录。",
        "sr_stat_reviews": "审查次数",
        "sr_stat_findings": "发现问题总数",
        "sr_sev_critical": "🔴 严重",
        "sr_sev_risk": "🟡 风险",
        "sr_sev_suggestion": "🟢 建议",
        "sr_top_categories": "**高频问题类别**",
        # --- CR report ---
        "sr_report_title": "## CR 报告",
        "sr_sec_critical": "### 🔴 严重问题（必须修复）",
        "sr_sec_risk": "### 🟡 潜在风险（建议修复）",
        "sr_sec_suggestion": "### 🟢 优化建议（可选）",
        "sr_none": "无",
        "sr_h_no": "序号",
        "sr_h_desc": "问题描述",
        "sr_h_loc": "代码位置",
        "sr_h_impact": "影响范围",
        "sr_h_risk": "风险说明",
        "sr_h_fix": "修复建议",
        "sr_h_opt": "优化建议",
        "sr_sec_lineage": "### 🔗 表级血缘",
        "sr_lin_sources": "来源表",
        "sr_lin_targets": "目标表",
        "sr_lin_none_target": "无（仅查询）",
        "sr_lin_columns": "列级血缘：",
        "sr_lin_agg": "（聚合）",
        "sr_sec_stats": "### 📊 检查统计",
        "sr_stats_total": "检查项总数",
        "sr_stats_passed": "通过",
        "sr_stats_problems": "问题",
        "sr_stats_risks": "风险",
        "sr_sec_verdict": "### 💡 总体评价",
        "sr_sum_critical": (
            "代码存在 {n} 个严重问题，会导致 SQL 执行错误或结果不正确，"
            "必须修复后才能上线。"
        ),
        "sr_sum_risk": (
            "代码无严重问题，但存在 {n} 个潜在风险，建议按优化建议修复后再上线。"
        ),
        "sr_sum_pass": "代码检查通过，未发现明显问题。",
        # --- agent / fixer ---
        "sr_no_sql": "没有可审查的 SQL。",
        "sr_fix_no_sql": "模型未返回可用的修复 SQL",
    },
}


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").strip().lower().startswith("en") else "zh"


def sr(lang: str, key: str) -> str:
    table = SR_I18N.get(lang) or SR_I18N["zh"]
    return table.get(key) or SR_I18N["zh"].get(key, key)


def catalog_label(category: str, lang: str) -> str:
    """Localized label for a CHECK_CATALOG category key."""
    if lang == "en":
        return CHECK_CATALOG_EN.get(category, category)
    from .report import CHECK_CATALOG
    return CHECK_CATALOG.get(category, category)
