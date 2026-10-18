"""Data Comparison Agent i18n dictionaries (EN/ZH)."""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)

DC_I18N: dict[str, dict[str, str]] = {
    "en": {
        "dc_compare_schema": "Schema Diff",
        "dc_compare_agg": "Aggregates",
        "dc_schema_result": "Schema Comparison",
        "dc_added": "Added",
        "dc_removed": "Removed",
        "dc_type_changed": "Type Changed",
        "dc_identical": "Schemas are identical",
        "dc_count_result": "Row Count Comparison",
        "dc_delta": "Delta",
        "dc_match": "Match",
        "dc_sample_result": "Sample Data Diff",
        "dc_added_rows": "Added rows",
        "dc_removed_rows": "Removed rows",
        "dc_no_diff": "No differences found",
        "dc_agg_result": "Aggregate Comparison",
        "dc_mismatch": "Mismatch",
        "dc_error": "Error",
        "dc_connect_both": "Please connect both data sources first",
        "dc_select_tables": "Please select tables on both sides",
        "dc_running": "Comparing...",
        "dc_port_not_number": "Port must be a number",
        "dc_host_required": "Host is required — enter it above or set {var} in .env",
        "dc_keyed_diff_fallback": "Key-based diff failed ({err}); showing positional diff instead",
        "dc_column": "Column",
        "dc_type_a": "Type (A)",
        "dc_type_b": "Type (B)",
        "dc_status": "Status",
        "dc_count_a": "Count (A)",
        "dc_count_b": "Count (B)",
        "dc_metric": "Metric",
        "dc_value_a": "Value (A)",
        "dc_value_b": "Value (B)",
        "dc_no_numeric": "No shared numeric columns",
        "dc_tables_loaded": "{n} tables loaded",
        # A — summary card
        "dc_summary": "Comparison Summary",
        "dc_comparisons_done": "{n} comparisons completed",
        "dc_diffs_found": "{n} difference(s) found",
        "dc_no_diffs": "All matched",
        "dc_elapsed": "elapsed {ms}ms",
        # B — batch count
        "dc_batch_result": "Batch Row Count",
        "dc_common_tables": "{n} common tables found",
        "dc_no_common": "No common tables between the two sources",
        "dc_table_name": "Table",
        # C — sample row preview
        "dc_sample_preview": "Preview",
        "dc_showing_n_rows": "Showing first {n} rows",
        # D — key-based diff
        "dc_key_diff": "Key-Based Diff",
        "dc_modified_rows": "Modified rows",
        "dc_old_val": "Old",
        "dc_new_val": "New",
        # E — custom SQL
        "dc_sql_readonly_only": "Only SELECT statements are allowed",
        # F — column profile
        "dc_profile_result": "Column Profile Comparison",
        "dc_distinct": "Distinct",
        "dc_null_rate": "Null %",
        "dc_min": "Min",
        "dc_max": "Max",
        # G — WHERE filter
        "dc_where_invalid": "WHERE clause contains forbidden keyword: {kw}",
        # H — report persistence
        "dc_loaded": "Report loaded",
        # I — table search
        # J — progress
        "dc_comparing_table": "Comparing {name}...",
        # K — report viewer
        "dc_report_title": "Data Comparison Report",
        "dc_no_report": "No report yet — run a comparison first",
        "dc_print": "Print",
        # L — connection presets
        # M — threshold alerts
        "dc_threshold_pass": "PASS",
        "dc_threshold_fail": "FAIL",
        # N — sync config
        "dc_sync_generated": "Sync config generated",
        # O — column mapping
        # P — scheduled comparison
        "dc_schedule_running": "Scheduled: next run in {m} min",
        "dc_schedule_stopped": "Schedule stopped",
        # Q — multi-table full comparison
        "dc_batch_full_result": "Batch Full Comparison",
        "dc_batch_summary": "{pass_n} passed, {fail_n} failed of {total} tables",
        "dc_batch_templates_hint": "Select templates to run in batch",
        "dc_batch_templates_result": "Batch Template Results",
        "dc_batch_templates_pass": "Pass",
        "dc_batch_templates_fail": "Fail",
        # R — sampling strategies
        # S — history trends
        "dc_alert_result": "Alert Results",
        "dc_alert_triggered": "TRIGGERED",
        "dc_alert_ok": "OK",
        "dc_alert_metric": "Metric",
        "dc_alert_threshold": "Threshold",
        "dc_alert_consecutive": "Consecutive",
        # T — incremental comparison
        "dc_watermark_hint": "e.g. updated_at",
        # U — data quality rules
        "dc_quality_rules_hint": "e.g. name:not_null>95, age:range:0-150",
        "dc_quality_result": "Quality Check Result",
        "dc_quality_pass": "PASS",
        "dc_quality_fail": "FAIL",
        # V — diff SQL generation
        "dc_diff_sql_result": "Generated SQL",
        "dc_diff_sql_no_diff": "No keyed diff result to generate SQL from",
        # W — comparison templates
        # X — webhook notification
        # Y — row-level drill-down
        "dc_drill_down": "Drill Down",
        "dc_row_values_a": "Row A values",
        "dc_row_values_b": "Row B values",
        # Z — data masking
        # AA — multi-environment
        "dc_env_hint": "e.g. dev, staging, prod",
        # BB — data skew
        "dc_skew_result": "Data Skew Analysis",
        "dc_skew_column": "Skew Column",
        "dc_skew_gini": "Gini",
        "dc_skew_cv": "CV",
        "dc_skew_top1": "Top-1 %",
        "dc_skew_ndv": "NDV",
        "dc_skew_no_columns": "Please specify columns to analyze",
        "dc_skew_verdict_mismatch": (
            "⛔ A/B distributions disagree on: {cols} — if B is synced from A "
            "this points at the sync pipeline (split/filter logic): fix the "
            "data first, don't tune the compute."
        ),
        "dc_skew_verdict_both": (
            "⚠️ Both sides skew the same way on: {cols} — a business fact "
            "(hot key). Protect downstream GROUP BY/JOIN on this key: see the "
            "Data Skew page for rewrites and engine settings."
        ),
        "dc_skew_goto_dataskew": "Analyze on Data Skew page →",
        # CC — checksum comparison
        "dc_checksum_result": "Checksum Comparison",
        "dc_checksum_segment": "Segment",
        "dc_checksum_match": "Match",
        "dc_checksum_mismatch": "Mismatch",
        "dc_checksum_all_match": "All segments match",
        # chunked (blocked) verification for large tables
        # custom-SQL result comparison card
        "dc_sqlres_title": "SQL Result Comparison",
        "dc_sqlres_match": "Result sets are identical",
        "dc_sqlres_summary": "{changed} changed · {only_a} only in A · {only_b} only in B",
        "dc_sqlres_changed": "Changed (matched by first column)",
        "dc_sqlres_only_a": "Only in A",
        "dc_sqlres_only_b": "Only in B",
        "dc_sqlres_alias_hint": "Tip: alias aggregate columns (e.g. SUM(amount) AS total) for readable column names",
        "dc_chunked_result": "Chunked Verification",
        "dc_chunked_need_pk": "Fill Key Columns with a numeric primary key first",
        "dc_chunked_all_match": "All chunks match",
        "dc_chunked_summary": "{chunks} chunks · {mismatched} mismatched · rows {ta}/{tb}",
        "dc_chunked_only_a": "Only in A",
        "dc_chunked_only_b": "Only in B",
        "dc_chunked_changed": "Changed",
        "dc_chunked_truncated": "drill-down truncated — narrow the WHERE filter to see the rest",
        # DD — partition comparison
        "dc_partition_result": "Partition Comparison",
        "dc_partition_col_hint": "Column to partition by",
        "dc_partition_value": "Partition Value",
        "dc_partition_delta": "Delta",
        "dc_partition_total_delta": "Total Absolute Delta",
        # EE — custom aggregate
        "dc_custom_agg_result": "Custom Aggregate Comparison",
        "dc_custom_agg_hint": "One per line: alias=EXPRESSION",
        "dc_custom_agg_expression": "Expression",
        "dc_custom_agg_alias": "Alias",
        # Phase 3 — multi-env, batch, trend
        "dc_env_compare_result": "Multi-Environment Result",
        "dc_batch_tpl_schema": "Schema",
        "dc_batch_tpl_agg": "Agg Mismatches",
        # Phase 5 — new features
        "dc_report_diff_result": "Report Diff Result",
        "dc_report_diff_section": "Section",
        "dc_report_diff_field": "Field",
        "dc_report_diff_old_val": "Old Value",
        "dc_report_diff_new_val": "New Value",
        "dc_report_diff_no_change": "No changes between reports",
        "dc_lineage_title": "Upstream Dependencies",
        "dc_lineage_hint": "SQL statements to trace lineage from (one per line)",
        "dc_lineage_no_deps": "No upstream dependencies found",
    },
    "zh": {
        "dc_compare_schema": "结构对比",
        "dc_compare_agg": "聚合对比",
        "dc_schema_result": "表结构对比",
        "dc_added": "新增",
        "dc_removed": "删除",
        "dc_type_changed": "类型变更",
        "dc_identical": "表结构完全一致",
        "dc_count_result": "行数对比",
        "dc_delta": "差异",
        "dc_match": "一致",
        "dc_sample_result": "样本数据差异",
        "dc_added_rows": "新增行",
        "dc_removed_rows": "删除行",
        "dc_no_diff": "未发现差异",
        "dc_agg_result": "聚合统计对比",
        "dc_mismatch": "不一致",
        "dc_error": "错误",
        "dc_connect_both": "请先连接两个数据源",
        "dc_select_tables": "请选择两侧的表",
        "dc_running": "比对中...",
        "dc_port_not_number": "端口号必须是数字",
        "dc_host_required": "请填写主机地址，或在 .env 中配置 {var}",
        "dc_keyed_diff_fallback": "按主键对比失败（{err}），已回退为按行位置对比",
        "dc_column": "字段",
        "dc_type_a": "类型 (A)",
        "dc_type_b": "类型 (B)",
        "dc_status": "状态",
        "dc_count_a": "行数 (A)",
        "dc_count_b": "行数 (B)",
        "dc_metric": "指标",
        "dc_value_a": "值 (A)",
        "dc_value_b": "值 (B)",
        "dc_no_numeric": "无共同数值列",
        "dc_tables_loaded": "已加载 {n} 张表",
        # A — summary card
        "dc_summary": "对比摘要",
        "dc_comparisons_done": "完成 {n} 项对比",
        "dc_diffs_found": "发现 {n} 项差异",
        "dc_no_diffs": "全部一致",
        "dc_elapsed": "耗时 {ms}ms",
        # B — batch count
        "dc_batch_result": "批量行数对比",
        "dc_common_tables": "找到 {n} 张同名表",
        "dc_no_common": "两个数据源无同名表",
        "dc_table_name": "表名",
        # C — sample row preview
        "dc_sample_preview": "预览",
        "dc_showing_n_rows": "展示前 {n} 行",
        # D — key-based diff
        "dc_key_diff": "基于主键对比",
        "dc_modified_rows": "修改行",
        "dc_old_val": "旧值",
        "dc_new_val": "新值",
        # E — custom SQL
        "dc_sql_readonly_only": "仅允许 SELECT 语句",
        # F — column profile
        "dc_profile_result": "字段画像对比",
        "dc_distinct": "去重数",
        "dc_null_rate": "空值率 %",
        "dc_min": "最小值",
        "dc_max": "最大值",
        # G — WHERE filter
        "dc_where_invalid": "WHERE 条件包含禁止关键字: {kw}",
        # H — report persistence
        "dc_loaded": "报告已加载",
        # I — table search
        # J — progress
        "dc_comparing_table": "正在对比 {name}...",
        # K — report viewer
        "dc_report_title": "数据比对报告",
        "dc_no_report": "暂无报告 — 请先执行对比",
        "dc_print": "打印",
        # L — connection presets
        # M — threshold alerts
        "dc_threshold_pass": "通过",
        "dc_threshold_fail": "未通过",
        # N — sync config
        "dc_sync_generated": "同步配置已生成",
        # O — column mapping
        # P — scheduled comparison
        "dc_schedule_running": "定时运行中：{m} 分钟后执行",
        "dc_schedule_stopped": "定时已停止",
        # Q — multi-table full comparison
        "dc_batch_full_result": "批量全量对比结果",
        "dc_batch_summary": "{total} 张表中 {pass_n} 通过，{fail_n} 未通过",
        "dc_batch_templates_hint": "选择要批量运行的模板",
        "dc_batch_templates_result": "批量模板结果",
        "dc_batch_templates_pass": "通过",
        "dc_batch_templates_fail": "失败",
        # R — sampling strategies
        # S — history trends
        "dc_alert_result": "告警结果",
        "dc_alert_triggered": "已触发",
        "dc_alert_ok": "正常",
        "dc_alert_metric": "指标",
        "dc_alert_threshold": "阈值",
        "dc_alert_consecutive": "连续次数",
        # T — incremental comparison
        "dc_watermark_hint": "例如 updated_at",
        # U — data quality rules
        "dc_quality_rules_hint": "例如 name:not_null>95, age:range:0-150",
        "dc_quality_result": "质量检查结果",
        "dc_quality_pass": "通过",
        "dc_quality_fail": "未通过",
        # V — diff SQL generation
        "dc_diff_sql_result": "生成的 SQL",
        "dc_diff_sql_no_diff": "没有主键差异结果可生成 SQL",
        # W — comparison templates
        # X — webhook notification
        # Y — row-level drill-down
        "dc_drill_down": "行级展开",
        "dc_row_values_a": "A 行数据",
        "dc_row_values_b": "B 行数据",
        # Z — data masking
        # AA — multi-environment
        "dc_env_hint": "例如 dev, staging, prod",
        # BB — data skew
        "dc_skew_result": "数据倾斜分析",
        "dc_skew_column": "倾斜分析列",
        "dc_skew_gini": "基尼系数",
        "dc_skew_cv": "变异系数",
        "dc_skew_top1": "Top-1 占比",
        "dc_skew_ndv": "去重值数",
        "dc_skew_no_columns": "请指定要分析的列",
        "dc_skew_verdict_mismatch": (
            "⛔ 两侧分布不一致：{cols}——若 B 应同步自 A，先排查同步链路"
            "（分片/过滤逻辑），修数据而不是调计算。"
        ),
        "dc_skew_verdict_both": (
            "⚠️ 两侧一致倾斜：{cols}——业务事实（热 key）。下游按该键 "
            "GROUP BY/JOIN 时建议到「数据倾斜」页做改写与引擎参数防护。"
        ),
        "dc_skew_goto_dataskew": "去数据倾斜页分析 →",
        # CC — checksum comparison
        "dc_checksum_result": "校验和比对",
        "dc_checksum_segment": "分段",
        "dc_checksum_match": "匹配",
        "dc_checksum_mismatch": "不匹配",
        "dc_checksum_all_match": "所有分段均匹配",
        # 大表分块校验
        # 自定义 SQL 结果对比卡
        "dc_sqlres_title": "SQL 结果对比",
        "dc_sqlres_match": "两侧结果完全一致",
        "dc_sqlres_summary": "{changed} 组变更 · 仅 A 侧 {only_a} · 仅 B 侧 {only_b}",
        "dc_sqlres_changed": "变更(按第一列配对)",
        "dc_sqlres_only_a": "仅 A 侧存在",
        "dc_sqlres_only_b": "仅 B 侧存在",
        "dc_sqlres_alias_hint": "提示:给聚合列起别名(如 SUM(amount) AS total)可获得可读列名",
        "dc_chunked_result": "分块校验",
        "dc_chunked_need_pk": "请先在主键列填入数值主键列",
        "dc_chunked_all_match": "全部分块一致",
        "dc_chunked_summary": "{chunks} 个分块 · {mismatched} 个不一致 · 行数 {ta}/{tb}",
        "dc_chunked_only_a": "仅 A 侧存在",
        "dc_chunked_only_b": "仅 B 侧存在",
        "dc_chunked_changed": "内容不同",
        "dc_chunked_truncated": "下钻结果被截断——收窄 WHERE 条件查看其余差异",
        # DD — partition comparison
        "dc_partition_result": "分区比对结果",
        "dc_partition_col_hint": "按此列分区统计",
        "dc_partition_value": "分区值",
        "dc_partition_delta": "差异",
        "dc_partition_total_delta": "总绝对差异",
        # EE — custom aggregate
        "dc_custom_agg_result": "自定义聚合比对",
        "dc_custom_agg_hint": "每行一个：别名=表达式",
        "dc_custom_agg_expression": "表达式",
        "dc_custom_agg_alias": "别名",
        # Phase 3 — multi-env, batch, trend
        "dc_env_compare_result": "跨环境对比结果",
        "dc_batch_tpl_schema": "结构",
        "dc_batch_tpl_agg": "聚合不一致",
        # Phase 5 — new features
        "dc_report_diff_result": "报告对比结果",
        "dc_report_diff_section": "模块",
        "dc_report_diff_field": "字段",
        "dc_report_diff_old_val": "旧值",
        "dc_report_diff_new_val": "新值",
        "dc_report_diff_no_change": "两份报告无差异",
        "dc_lineage_title": "上游依赖",
        "dc_lineage_hint": "用于溯源的SQL语句（每行一条）",
        "dc_lineage_no_deps": "未发现上游依赖",
    },
}


def dc(lang: str, key: str) -> str:
    """Look up a UI string by language and key."""
    value = DC_I18N.get(lang, DC_I18N["en"]).get(key, DC_I18N["en"].get(key))
    if value is None:
        _logger.debug("Missing i18n key: %s", key)
        return key
    return value
