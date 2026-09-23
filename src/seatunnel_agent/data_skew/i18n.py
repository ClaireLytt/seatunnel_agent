# -*- coding: utf-8 -*-
"""EN/ZH strings for the Data Skew page and report rendering.

Mirrors the ``data_comparison.i18n`` pattern: one flat dict per language,
looked up via ``dsk(lang, key)`` with Chinese as the fallback (the source
language of the detector findings).
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)

DSK_I18N: dict[str, dict[str, str]] = {
    "en": {
        # --- UI chrome ---
        "dsk_title": "## ⚖️ SQL Data Skew Analyzer",
        "dsk_subtitle": (
            "Static skew-pattern rules + LLM rewrite. Supports Spark SQL (Spark 3) "
            "and MaxCompute SQL (Hive accepted as compatible input). Pure static "
            "analysis — the SQL is never executed and no connection is required."
        ),
        "dsk_sql_placeholder": "Paste the SQL to analyze for data skew…",
        "dsk_dialect": "SQL Dialect",
        "dsk_mode": "Analysis Mode",
        "dsk_mode_static": "Static scan (fast, no LLM)",
        "dsk_mode_llm": "LLM optimize (rewrite SQL)",
        "dsk_analyze_btn": "Analyze Skew",
        "dsk_clear_btn": "Clear",
        "dsk_report_placeholder": "*The skew analysis report will appear here*",
        "dsk_optimized_sql": "Optimized SQL",
        "dsk_download_sql": "Download Optimized SQL (.sql)",
        "dsk_download_report": "Download Report (.md)",
        "dsk_lang": "Language",
        "dsk_empty_sql": "❌ Please paste a SQL script first.",
        "dsk_llm_unavailable": (
            "⚠️ LLM is not configured (missing API key) — showing static scan only."
        ),
        "dsk_running_static": "Running static skew scan…",
        "dsk_running_llm": "LLM is analyzing and rewriting the SQL…",
        "dsk_error": "Error",
        # --- report chrome ---
        "rpt_title": "# 📊 Data Skew Analysis Report",
        "rpt_dialect": "Dialect",
        "rpt_stmt_count": "Statements",
        "rpt_summary": "## Summary",
        "rpt_findings": "## Skew Findings",
        "rpt_no_findings": "✅ No skew risk patterns detected by static rules.",
        "rpt_sev_high": "🔴 High skew risk (fix strongly recommended)",
        "rpt_sev_medium": "🟡 Potential skew (review recommended)",
        "rpt_sev_low": "🔵 Optimization hint (optional)",
        "rpt_col_idx": "#",
        "rpt_col_category": "Category",
        "rpt_col_location": "Location",
        "rpt_col_desc": "Problem",
        "rpt_col_impact": "Impact",
        "rpt_col_suggestion": "Suggestion",
        "rpt_opt_title": "## Optimization Points",
        "rpt_col_point": "Optimization",
        "rpt_col_before": "Original",
        "rpt_col_after": "Optimized",
        "rpt_col_benefit": "Expected Benefit",
        "rpt_line": "line {n}",
        "rpt_stmt": "statement {n}",
        "rpt_source_linter": "static",
        "rpt_source_llm": "LLM",
        "rpt_consistency": "## Consistency Check",
        "rpt_optimized_file": "Optimized SQL written to",
        "rpt_verdict_high": "⛔ High skew risk: {n} high-risk pattern(s) found — fix before running on large data.",
        "rpt_verdict_medium": "⚠️ Potential skew: {n} finding(s) worth reviewing.",
        "rpt_verdict_clean": "✅ No obvious skew pattern found at the syntax level.",
        "rpt_engine_hints": "## Engine-Level Hints",
    },
    "zh": {
        # --- UI chrome ---
        "dsk_title": "## ⚖️ SQL 数据倾斜分析",
        "dsk_subtitle": (
            "静态倾斜规则 + LLM 改写。支持 Spark SQL（Spark 3）与 MaxCompute SQL"
            "（Hive 作为兼容输入）。纯语法级静态分析——不执行 SQL，无需连接数据源。"
        ),
        "dsk_sql_placeholder": "粘贴需要分析数据倾斜的 SQL 脚本…",
        "dsk_dialect": "SQL 方言",
        "dsk_mode": "分析模式",
        "dsk_mode_static": "静态扫描（快速，不调用 LLM）",
        "dsk_mode_llm": "LLM 优化（改写 SQL）",
        "dsk_analyze_btn": "开始分析",
        "dsk_clear_btn": "清空",
        "dsk_report_placeholder": "*倾斜分析报告将显示在这里*",
        "dsk_optimized_sql": "优化后 SQL",
        "dsk_download_sql": "下载优化后 SQL（.sql）",
        "dsk_download_report": "下载报告（.md）",
        "dsk_lang": "语言",
        "dsk_empty_sql": "❌ 请先粘贴 SQL 脚本。",
        "dsk_llm_unavailable": "⚠️ LLM 未配置（缺少 API Key）——仅展示静态扫描结果。",
        "dsk_running_static": "正在执行静态倾斜扫描…",
        "dsk_running_llm": "LLM 正在分析并改写 SQL…",
        "dsk_error": "错误",
        # --- report chrome ---
        "rpt_title": "# 📊 数据倾斜分析报告",
        "rpt_dialect": "方言",
        "rpt_stmt_count": "语句数",
        "rpt_summary": "## 总体结论",
        "rpt_findings": "## 倾斜风险明细",
        "rpt_no_findings": "✅ 静态规则未发现明显的倾斜风险写法。",
        "rpt_sev_high": "🔴 高倾斜风险（强烈建议修复）",
        "rpt_sev_medium": "🟡 潜在倾斜（建议排查）",
        "rpt_sev_low": "🔵 优化建议（可选）",
        "rpt_col_idx": "#",
        "rpt_col_category": "类别",
        "rpt_col_location": "位置",
        "rpt_col_desc": "问题描述",
        "rpt_col_impact": "影响",
        "rpt_col_suggestion": "优化建议",
        "rpt_opt_title": "## 优化点说明",
        "rpt_col_point": "优化点",
        "rpt_col_before": "原写法",
        "rpt_col_after": "优化后",
        "rpt_col_benefit": "预期收益",
        "rpt_line": "行 {n}",
        "rpt_stmt": "语句 {n}",
        "rpt_source_linter": "静态",
        "rpt_source_llm": "LLM",
        "rpt_consistency": "## 一致性检查",
        "rpt_optimized_file": "优化后 SQL 已写入",
        "rpt_verdict_high": "⛔ 高倾斜风险：发现 {n} 处高风险写法——建议在大数据量运行前修复。",
        "rpt_verdict_medium": "⚠️ 潜在倾斜：{n} 处发现值得排查。",
        "rpt_verdict_clean": "✅ 语法层面未发现明显倾斜写法。",
        "rpt_engine_hints": "## 引擎参数建议",
    },
}


def normalize_lang(lang: str | None) -> str:
    l = (lang or "zh").strip().lower()
    if l.startswith("en"):
        return "en"
    return "zh"


def dsk(lang: str, key: str) -> str:
    """Look up a UI/report string; falls back to Chinese, then to the key."""
    lang = normalize_lang(lang)
    val = DSK_I18N.get(lang, {}).get(key)
    if val is None:
        val = DSK_I18N["zh"].get(key)
    if val is None:
        _logger.warning("data_skew i18n missing key: %s", key)
        return key
    return val
