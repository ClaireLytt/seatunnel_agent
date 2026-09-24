# -*- coding: utf-8 -*-
"""EN/ZH strings for the SQL Review page and CR report rendering.

Mirrors the ``data_comparison.i18n`` pattern: one flat dict per language,
looked up via ``sr(lang, key)`` with Chinese as the fallback (the source
language of the linter findings).
"""

from __future__ import annotations

# English labels for report.CHECK_CATALOG (keys must stay in sync).
CHECK_CATALOG_EN: dict[str, str] = {
    "syntax": "SQL syntax validity (dialect parse)",
    "schema_ref": "Table/column existence (schema check)",
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
            "Static rules + LLM semantic review. Supports Hive / Spark / Flink / "
            "MaxCompute / MySQL / PostgreSQL / SQL Server / ClickHouse / Doris / "
            "SQLite. Pure static analysis — the SQL is never executed."
        ),
        "sr_sql_placeholder": "Paste the SQL to review…",
        "sr_dialect": "SQL Dialect",
        "sr_mode": "Review Mode",
        "sr_mode_static": "Static review (fast, no LLM)",
        "sr_mode_llm": "LLM deep review",
        "sr_ddl_accordion": "Table DDL (optional, for schema checks)",
        "sr_ddl_label": "CREATE TABLE statements",
        "sr_rules_accordion": "Rule config (optional, .sqlreview.yaml format)",
        "sr_rules_label": "YAML rules",
        "sr_rules_placeholder": (
            "partition_columns: [dt, ds]\nthresholds:\n  max_joins: 5"
        ),
        "sr_rules_invalid": "❌ **Invalid rule config**",
        "sr_download_report": "Download Report (.md)",
        "sr_review_btn": "Start Review",
        "sr_fix_btn": "Generate Fixed SQL (LLM)",
        "sr_clear_btn": "Clear",
        "sr_report_placeholder": "*The review report will appear here*",
        "sr_fixed_sql": "Fixed SQL",
        "sr_stats_accordion": "📈 Review History Stats",
        "sr_stats_placeholder": "*Click refresh to load*",
        "sr_refresh": "Refresh Stats",
        # --- UI dynamic messages ---
        "sr_input_sql_first": "Please enter SQL first.",
        "sr_review_failed": "❌ **Review failed**",
        "sr_fix_need_review": "-- Run a review first",
        "sr_fix_generating": "-- Calling the LLM to generate fixed SQL, please wait…",
        "sr_fix_failed": "-- Fix failed",
        "sr_fix_none_static": "-- No mechanically fixable issue found; switch to LLM review mode for a full rewrite",
        "sr_cache_hit": "Review cache hit (same SQL / dialect / rules) — skipping the LLM call",
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
            "静态规则 + LLM 语义审查，支持 Hive / Spark / Flink / MaxCompute / "
            "MySQL / PostgreSQL / SQL Server / ClickHouse / Doris / SQLite。"
            "纯静态分析，不执行 SQL。"
        ),
        "sr_sql_placeholder": "粘贴要审查的 SQL……",
        "sr_dialect": "SQL 方言",
        "sr_mode": "审查模式",
        "sr_mode_static": "静态审查（快速，无需 LLM）",
        "sr_mode_llm": "LLM 深度审查",
        "sr_ddl_accordion": "表结构 DDL（可选，用于 schema 校验）",
        "sr_ddl_label": "CREATE TABLE 语句",
        "sr_rules_accordion": "规则配置（可选，.sqlreview.yaml 格式）",
        "sr_rules_label": "YAML 规则",
        "sr_rules_placeholder": (
            "partition_columns: [dt, ds]\nthresholds:\n  max_joins: 5"
        ),
        "sr_rules_invalid": "❌ **规则配置无效**",
        "sr_download_report": "下载报告（.md）",
        "sr_review_btn": "开始审查",
        "sr_fix_btn": "生成修复 SQL（LLM）",
        "sr_clear_btn": "清空",
        "sr_report_placeholder": "*审查报告将显示在这里*",
        "sr_fixed_sql": "修复后 SQL",
        "sr_stats_accordion": "📈 审查历史统计",
        "sr_stats_placeholder": "*点击刷新查看*",
        "sr_refresh": "刷新统计",
        # --- UI dynamic messages ---
        "sr_input_sql_first": "请先输入 SQL。",
        "sr_review_failed": "❌ **审查失败**",
        "sr_fix_need_review": "-- 请先完成一次审查",
        "sr_fix_generating": "-- 正在调用 LLM 生成修复 SQL，请稍候……",
        "sr_fix_failed": "-- 修复失败",
        "sr_fix_none_static": "-- 没有可静态自动修复的问题；如需完整改写请切换到 LLM 审查模式",
        "sr_cache_hit": "命中审查缓存（相同 SQL/方言/规则），跳过 LLM 调用",
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


# English templates for linter rule texts. Finding.key selects the entry,
# Finding.args fills the {placeholders}. Chinese stays the source language
# on the Finding itself; these are applied at render time for lang="en".
RULE_TEXTS_EN: dict[str, dict[str, str]] = {
    "groupby_missing": {
        "description": "GROUP BY is missing {cols}",
        "impact": "Incorrect results",
        "suggestion": "GROUP BY must include every non-aggregated column",
    },
    "cross_join": {
        "description": "CROSS JOIN (Cartesian product) used",
        "impact": "Row-count explosion",
        "suggestion": "Confirm the Cartesian product is intended; otherwise use a JOIN with an ON condition",
    },
    "join_no_on": {
        "description": "JOIN has no ON condition (Cartesian product)",
        "impact": "Row-count explosion / wrong results",
        "suggestion": "Add a proper ON condition to the JOIN",
    },
    "join_on_or": {
        "description": "OR inside a JOIN ON condition",
        "impact": "May cause many-to-many blowup and prevents efficient join strategies",
        "suggestion": "Split into UNION ALL branches or rewrite the join logic",
    },
    "join_non_equi": {
        "description": "Non-equi JOIN condition",
        "impact": "May cause many-to-many row amplification",
        "suggestion": "Verify the join keys; prefer equality joins",
    },
    "join_key_type": {
        "description": "Join key type mismatch: {left} ({ltype}) = {right} ({rtype})",
        "impact": "Implicit casts can break matches, produce wrong results, or cause skew",
        "suggestion": "CAST both sides to a common type explicitly before joining",
    },
    "comma_join_style": {
        "description": "Implicit comma join at line {line}",
        "impact": "Join predicates hidden in WHERE hurt readability and are easy to miss",
        "suggestion": "Rewrite as an explicit JOIN ... ON",
    },
    "comma_join_cartesian": {
        "description": "Comma join with no join predicate (Cartesian product)",
        "impact": "Row-count explosion / wrong results",
        "suggestion": "Rewrite as an explicit JOIN ... ON with proper join keys",
    },
    "null_eq": {
        "description": "NULL compared with {op}",
        "impact": "The predicate never matches; wrong results",
        "suggestion": "Use {fixed}",
    },
    "div_zero_const": {
        "description": "Division by literal 0",
        "impact": "Division-by-zero error",
        "suggestion": "Fix the calculation; never divide by zero",
    },
    "div_no_guard": {
        "description": "Division by {denom} without a zero guard",
        "impact": "A zero or NULL denominator yields errors or unexpected results",
        "suggestion": "Use / NULLIF({denom}, 0)",
    },
    "partition_missing": {
        "description": "Table {table} has no partition filter",
        "impact": "Full table scan",
        "suggestion": "Add a partition predicate such as pt = '${{bizdate}}'",
    },
    "partition_numeric": {
        "description": "Partition predicate {col} = {val} uses a numeric literal",
        "impact": "Implicit type conversion can disable partition pruning",
        "suggestion": "Use {col} = '{val}'",
    },
    "select_star": {
        "description": "SELECT * reads every column",
        "impact": "Unnecessary wide scan; column pruning disabled",
        "suggestion": "Select only the columns you need",
    },
    "order_by_no_limit": {
        "description": "Global ORDER BY without LIMIT",
        "impact": "Single-reducer global sort; very slow",
        "suggestion": "Add LIMIT, or use SORT BY / DISTRIBUTE BY",
    },
    "union_dedup": {
        "description": "UNION at line {line} triggers deduplication",
        "impact": "Extra deduplication cost",
        "suggestion": "Use UNION ALL when deduplication is not needed",
    },
    "count_distinct": {
        "description": "COUNT(DISTINCT) at line {line} can skew on large data",
        "impact": "Single-point aggregation may skew",
        "suggestion": "For large data, dedup with a two-stage GROUP BY then count",
    },
    "insert_overwrite_no_partition": {
        "description": "INSERT OVERWRITE {table} without PARTITION",
        "impact": "Overwrites the entire table",
        "suggestion": "Specify PARTITION(pt='${{bizdate}}') to overwrite only the target partition",
    },
    "dml_no_where": {
        "description": "{verb} {table} has no WHERE clause",
        "impact": "Updates/deletes every row in the table",
        "suggestion": "Add a WHERE clause; if a full-table operation is intended, state it in a comment",
    },
    "leading_wildcard_like": {
        "description": "LIKE with a leading wildcard '%...'",
        "impact": "Cannot use an index; full table scan",
        "suggestion": "Prefer prefix matching 'xxx%', or use a full-text index",
    },
    "where_func_on_column": {
        "description": "Function {func}(...) applied to a column in WHERE",
        "impact": "Disables index usage; may cause a full scan",
        "suggestion": "Rewrite as a range predicate computed on the constant side, e.g. col >= '...' AND col < '...'",
    },
    "deep_offset": {
        "description": "Deep pagination OFFSET {off}",
        "impact": "Scans and discards the first {off} rows; each page gets slower",
        "suggestion": "Use keyset pagination (WHERE id > last_page_id ORDER BY id LIMIT n)",
    },
    "clickhouse_final": {
        "description": "Query uses the FINAL modifier",
        "impact": "FINAL forces merge-on-read and significantly slows queries",
        "suggestion": "Use argMax / GROUP BY to read the latest version, or rely on background merges",
    },
    "readability_no_comment": {
        "description": "Long SQL with no comments",
        "impact": "Poor readability",
        "suggestion": "Add comments to the complex sections",
    },
    "subquery_depth": {
        "description": "Subqueries nested {depth} levels deep (threshold {max})",
        "impact": "Deep nesting is hard to read, maintain, and optimize",
        "suggestion": "Flatten the subqueries with WITH (CTEs)",
    },
    "too_many_joins": {
        "description": "{joins} JOINs in one statement (threshold {max})",
        "impact": "Complex execution plans that are hard to debug",
        "suggestion": "Split into intermediate tables / CTEs",
    },
    "stmt_too_long": {
        "description": "Statement is {lines} lines long (threshold {max})",
        "impact": "Very long statements are hard to review and maintain",
        "suggestion": "Split into multiple steps or views",
    },
    "distinct_with_groupby": {
        "description": "DISTINCT together with GROUP BY at line {line}",
        "impact": "Redundant deduplication",
        "suggestion": "GROUP BY already deduplicates; drop DISTINCT",
    },
    "syntax_error": {
        "description": "SQL parse failed: {error}",
        "impact": "The statement is likely to fail at runtime",
        "suggestion": "Fix the syntax error before further review",
    },
    "unknown_table": {
        "description": "Table {table} not found in the provided schema",
        "impact": "The statement will fail, or the schema info is stale",
        "suggestion": "Check the table name, or update the DDL / connection",
    },
    "unknown_column": {
        "description": "Column {column} not found in table {table}",
        "impact": "The statement will fail, or the schema info is stale",
        "suggestion": "Check the column name against the table definition",
    },
    "select_star_wide": {
        "description": "SELECT * on {table} expands to {n} columns",
        "impact": "Reads far more data than needed",
        "suggestion": "Select only the columns you need",
    },
    "not_partition_column": {
        "description": "{col} is filtered as a partition column but {table} is not partitioned by it",
        "impact": "The predicate does not prune partitions",
        "suggestion": "Filter on the table's real partition column(s): {parts}",
    },
    "explain_full_scan": {
        "description": "EXPLAIN confirms a full table scan on {table}",
        "impact": "The query does not hit an index; slow on large tables",
        "suggestion": "Index the filter column(s), or rewrite the query to use an existing index",
    },
}


def finding_texts(finding, lang: str) -> tuple[str, str, str]:
    """(description, impact, suggestion) localized for *lang*.

    Chinese is the source language stored on the Finding; English comes from
    RULE_TEXTS_EN via finding.key/args. Findings without a key (LLM output,
    custom rules) pass through unchanged.
    """
    if lang == "en" and getattr(finding, "key", ""):
        t = RULE_TEXTS_EN.get(finding.key)
        if t:
            try:
                args = finding.args or {}
                return (
                    t["description"].format(**args),
                    t["impact"].format(**args),
                    t["suggestion"].format(**args),
                )
            except (KeyError, IndexError):
                pass
    return finding.description, finding.impact, finding.suggestion


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
