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
            "and MaxCompute SQL (Hive accepted as compatible input). Static analysis "
            "by default — optionally connect a data source to verify skew with real "
            "key distributions."
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
        # --- datasource connection (optional) ---
        "dsk_conn_accordion": "Connect data source (optional — verify skew with real data)",
        "dsk_preset_dd": "Saved connection",
        "dsk_preset_load": "Load saved connections",
        "dsk_preset_none": "No saved connections — add one on the Settings page.",
        "dsk_preset_unsupported": "⚠️ Connection type '{t}' cannot run probes (LIMIT-incompatible).",
        "dsk_ds_type": "Datasource type",
        "dsk_host": "Host",
        "dsk_port": "Port",
        "dsk_db": "Database",
        "dsk_user": "Username",
        "dsk_pwd": "Password",
        "dsk_connect_btn": "Connect",
        "dsk_conn_status_none": "Not connected",
        "dsk_conn_ok": "✅ Connected: {info}",
        "dsk_conn_fail": "❌ Connection failed: {err}",
        "dsk_verify_btn": "Verify Skew (live data)",
        "dsk_verify_running": "Probing key distributions on the database…",
        "dsk_verify_need_conn": "⚠️ Connect a data source first.",
        "dsk_verify_need_analyze": "⚠️ Run an analysis first, then verify.",
        "dsk_sample": "Probe sampling",
        "dsk_sample_full": "Full scan (no sampling)",
        # --- SQL file upload / analysis history ---
        "dsk_upload_btn": "Upload SQL file",
        "dsk_history_accordion": "Analysis history (last 20)",
        "dsk_history_refresh": "Refresh",
        "dsk_history_load": "Load selected",
        "dsk_history_pick": "Pick a record",
        "dsk_history_empty": "*No history yet — run an analysis first.*",
        "dsk_h_time": "Time",
        "dsk_h_source": "Source",
        "dsk_h_dialect": "Dialect",
        "dsk_h_mode": "Mode",
        "dsk_h_findings": "Findings",
        "dsk_h_sql": "SQL",
        # --- probe section ---
        "prb_section": "## Skew Verification (measured)",
        "prb_no_targets": (
            "No probeable base-table keys were found in the script "
            "(subquery-only keys cannot be probed)."
        ),
        "prb_summary_confirmed": "⛔ Measured data confirms skew on {n} key(s).",
        "prb_summary_clean": "✅ No significant skew measured on the probed keys.",
        "prb_col_target": "Table.Column",
        "prb_col_reason": "Probed because",
        "prb_col_rows": "Rows",
        "prb_col_null": "NULL ratio",
        "prb_col_top": "Top values (share)",
        "prb_col_verdict": "Verdict",
        "prb_reason_join_key": "join key",
        "prb_reason_count_distinct": "COUNT(DISTINCT) column",
        "prb_reason_group_key": "GROUP BY key",
        "prb_reason_window_key": "window PARTITION BY key",
        "prb_reason_distinct_key": "leading DISTINCT column",
        "prb_verdict_confirmed": "⛔ skew confirmed",
        "prb_verdict_suspect": "⚠️ mild skew",
        "prb_verdict_ok": "✅ balanced",
        "prb_verdict_empty": "empty table",
        "prb_verdict_error": "probe failed",
        "prb_sampled_note": "(estimated from a {pct}% table sample)",
        "prb_engine_params": "**Suggested engine settings (based on measured skew)**",
        "prb_rewrite_head": "**Rewrite templates (from measured values — fill in the column lists)**",
        "prb_storage_head": "**Storage / modeling-layer advice (based on measured skew)**",
        # --- SeaTunnel split-key check ---
        "spk_accordion": "SeaTunnel split-key check (paste a job config)",
        "spk_conf_placeholder": (
            "Paste the SeaTunnel job config (HOCON) — the JDBC source's "
            "partition_column will be measured against the connected database…"
        ),
        "spk_btn": "Check split key",
        "spk_need_conn": "⚠️ Connect a data source first (the split key is measured on real data).",
        "spk_empty_conf": "❌ Paste a SeaTunnel job config first.",
        "spk_parse_fail": "❌ Could not parse the config: {err}",
        "spk_no_source": "❌ No source block with a table/query was found in the config.",
        "spk_no_table": (
            "❌ Could not resolve a base table from the source block "
            "(complex query — set table_path or simplify the query)."
        ),
        "spk_section": "## SeaTunnel Split-Key Check (measured)",
        "spk_configured": "Configured `partition_column`",
        "spk_none_configured": (
            "No `partition_column` configured — the source reads single-threaded; "
            "pick a uniform column below to enable parallel reads."
        ),
        "spk_col_column": "Column",
        "spk_col_rows": "Rows",
        "spk_col_ndv": "NDV",
        "spk_col_null": "NULL ratio",
        "spk_col_top1": "Top-1 share",
        "spk_col_verdict": "Verdict",
        "spk_verdict_good": "✅ uniform — good split key",
        "spk_verdict_suspect": "⚠️ mildly skewed — usable, watch task balance",
        "spk_verdict_bad": "⛔ skewed — one task will read most of the data",
        "spk_verdict_low_ndv": "⛔ NDV too low for the configured parallelism",
        "spk_verdict_null": "⛔ NULL-heavy — NULL rows funnel into one split",
        "spk_verdict_error": "probe failed",
        "spk_candidates": "**Candidate split columns (measured, best first)**",
        "spk_no_candidates": (
            "No numeric/date candidate columns could be measured on this table."
        ),
        "spk_snippet_head": "**Suggested source config**",
        "spk_sampled_note": "(estimated from a {pct}% table sample)",
        "spk_sink_note": (
            "The same column choice applies to the sink side: a skewed "
            "Doris/ClickHouse bucket key materializes this skew into storage."
        ),
        "spk_recheck_improved": (
            "🔁 Re-check vs last run ({ts}, key=`{pk}`, verdict {pv}) → now "
            "{cv} — ✅ the split-key issue is resolved, loop closed."
        ),
        "spk_recheck_regressed": (
            "🔁 Re-check vs last run ({ts}, key=`{pk}`, verdict {pv}) → now "
            "{cv} — ⚠️ regression: the key measured fine before, check for "
            "data drift."
        ),
        "spk_recheck_still_bad": (
            "🔁 Re-check vs last run ({ts}, key=`{pk}`, verdict {pv}) → now "
            "{cv} — ⚠️ still unresolved: switch partition_column to a ranked "
            "candidate and re-check."
        ),
        "spk_apply_fail": (
            "❌ Could not anchor the edit in the config text — nothing was "
            "changed."
        ),
        "spk_apply_done": (
            "✅ Split key written back to the config: {opt} = \"{col}\" "
            "(original backed up as {bak}). Re-run the check to verify."
        ),
        "spk_apply_none": (
            "ℹ️ Nothing to write back: no usable (good/suspect) key was "
            "measured, or the configured key is already the best choice."
        ),
        "dsk_conn_handoff": (
            "🔗 Connection handed over from Data Comparison side B "
            "({ds} {host}:{port}/{db}) — enter the password and click Connect."
        ),
        "dsk_conn_handoff_unsupported": (
            "⚠️ The data source handed over from Data Comparison ({t}) does "
            "not support live probing here — pick a supported type manually."
        ),
        # --- consistency measurement ---
        "cst_btn": "Measure Consistency (runs both SQLs)",
        "cst_running": "Running the original and the optimized SQL for comparison…",
        "cst_need_opt": "⚠️ Generate the optimized SQL first (LLM mode).",
        "cst_section": "## Consistency Measurement (original vs optimized)",
        "cst_not_single": (
            "Only a single SELECT / WITH statement can be measured — the script "
            "contains multiple statements or write operations, so it was not executed."
        ),
        "cst_error": "❌ Measurement failed: {err}",
        "cst_mismatch": (
            "⛔ Row counts differ: original {a} vs optimized {b} — review the rewrite."
        ),
        "cst_match_full": "✅ Row counts match and all {n} rows are identical.",
        "cst_rows_differ": (
            "⛔ Same row count but the row contents differ — review the rewrite."
        ),
        "cst_match_count": (
            "✅ Row counts match (result too large for a row-level diff)."
        ),
        "cst_agg_match": (
            "✅ Row counts match, and per-column COUNT / COUNT DISTINCT / MIN / MAX "
            "agree on all {n} shared column(s) (result too large for a row-level diff)."
        ),
        "cst_agg_differ": (
            "⛔ Same row count but per-column aggregates differ across the {n} "
            "shared column(s) — review the rewrite."
        ),
        "cst_col_metric": "Metric",
        "cst_col_orig": "Original SQL",
        "cst_col_opt": "Optimized SQL",
        "cst_rows": "Row count",
        "cst_elapsed": "Elapsed",
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
            "（Hive 作为兼容输入）。默认纯静态分析不执行 SQL；"
            "可选连接数据源，用真实键值分布验证倾斜。"
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
        # --- datasource connection (optional) ---
        "dsk_conn_accordion": "连接数据源（可选——用真实数据验证倾斜）",
        "dsk_preset_dd": "已保存连接",
        "dsk_preset_load": "读取已保存连接",
        "dsk_preset_none": "暂无已保存连接——可在设置页添加。",
        "dsk_preset_unsupported": "⚠️ 连接类型 '{t}' 不支持探查（不兼容 LIMIT）。",
        "dsk_ds_type": "数据源类型",
        "dsk_host": "主机",
        "dsk_port": "端口",
        "dsk_db": "数据库",
        "dsk_user": "用户名",
        "dsk_pwd": "密码",
        "dsk_connect_btn": "连接",
        "dsk_conn_status_none": "未连接",
        "dsk_conn_ok": "✅ 已连接：{info}",
        "dsk_conn_fail": "❌ 连接失败：{err}",
        "dsk_verify_btn": "验证倾斜（实测数据）",
        "dsk_verify_running": "正在探查数据库中键值分布…",
        "dsk_verify_need_conn": "⚠️ 请先连接数据源。",
        "dsk_verify_need_analyze": "⚠️ 请先执行一次分析，再进行验证。",
        "dsk_sample": "探查采样",
        "dsk_sample_full": "全量（不采样）",
        # --- SQL file upload / analysis history ---
        "dsk_upload_btn": "上传 SQL 文件",
        "dsk_history_accordion": "分析历史（最近 20 条）",
        "dsk_history_refresh": "刷新",
        "dsk_history_load": "载入所选",
        "dsk_history_pick": "选择记录",
        "dsk_history_empty": "*暂无历史记录——先执行一次分析。*",
        "dsk_h_time": "时间",
        "dsk_h_source": "来源",
        "dsk_h_dialect": "方言",
        "dsk_h_mode": "模式",
        "dsk_h_findings": "发现",
        "dsk_h_sql": "SQL",
        # --- probe section ---
        "prb_section": "## 倾斜验证（实测）",
        "prb_no_targets": "脚本中未解析到可探查的基表键（仅子查询内的键无法探查）。",
        "prb_summary_confirmed": "⛔ 实测数据确认 {n} 个键存在倾斜。",
        "prb_summary_clean": "✅ 探查的键未测得明显倾斜。",
        "prb_col_target": "表.列",
        "prb_col_reason": "探查原因",
        "prb_col_rows": "总行数",
        "prb_col_null": "NULL 占比",
        "prb_col_top": "Top 值（占比）",
        "prb_col_verdict": "判定",
        "prb_reason_join_key": "JOIN 关联键",
        "prb_reason_count_distinct": "COUNT(DISTINCT) 列",
        "prb_reason_group_key": "GROUP BY 分组键",
        "prb_reason_window_key": "窗口 PARTITION BY 键",
        "prb_reason_distinct_key": "DISTINCT 首列",
        "prb_verdict_confirmed": "⛔ 确认倾斜",
        "prb_verdict_suspect": "⚠️ 轻度倾斜",
        "prb_verdict_ok": "✅ 分布均衡",
        "prb_verdict_empty": "空表",
        "prb_verdict_error": "探查失败",
        "prb_sampled_note": "（按 {pct}% 表采样估算）",
        "prb_engine_params": "**建议引擎参数（基于实测倾斜）**",
        "prb_rewrite_head": "**改写模板（按实测值生成——列清单需自行补全）**",
        "prb_storage_head": "**存储/建模层建议（基于实测倾斜）**",
        # --- SeaTunnel split-key check ---
        "spk_accordion": "SeaTunnel 分片键体检（粘贴作业配置）",
        "spk_conf_placeholder": (
            "粘贴 SeaTunnel 作业配置（HOCON）——将连库实测 JDBC source 的 "
            "partition_column 分布是否均匀…"
        ),
        "spk_btn": "体检分片键",
        "spk_need_conn": "⚠️ 请先连接数据源（分片键需在真实数据上实测）。",
        "spk_empty_conf": "❌ 请先粘贴 SeaTunnel 作业配置。",
        "spk_parse_fail": "❌ 配置解析失败：{err}",
        "spk_no_source": "❌ 配置中未找到带 table/query 的 source 块。",
        "spk_no_table": "❌ 无法从 source 块解析出基表（查询较复杂——请配置 table_path 或简化 query）。",
        "spk_section": "## SeaTunnel 分片键体检（实测）",
        "spk_configured": "已配置的 `partition_column`",
        "spk_none_configured": (
            "未配置 `partition_column`——source 将单线程读取；"
            "可从下方候选列中选择均匀键开启并行读。"
        ),
        "spk_col_column": "列",
        "spk_col_rows": "总行数",
        "spk_col_ndv": "NDV（基数）",
        "spk_col_null": "NULL 占比",
        "spk_col_top1": "Top-1 占比",
        "spk_col_verdict": "判定",
        "spk_verdict_good": "✅ 分布均匀——适合作分片键",
        "spk_verdict_suspect": "⚠️ 轻度倾斜——可用，注意 task 均衡",
        "spk_verdict_bad": "⛔ 倾斜——单个 task 将读取大部分数据",
        "spk_verdict_low_ndv": "⛔ 基数过低，撑不起配置的并行度",
        "spk_verdict_null": "⛔ NULL 过多——NULL 行会集中到同一分片",
        "spk_verdict_error": "探查失败",
        "spk_candidates": "**候选分片列（实测，优先级从高到低）**",
        "spk_no_candidates": "该表未能实测到数值/日期类候选列。",
        "spk_snippet_head": "**建议的 source 配置**",
        "spk_sampled_note": "（按 {pct}% 表采样估算）",
        "spk_sink_note": (
            "写入端同理：Doris/ClickHouse 的分桶键若用该倾斜列，"
            "倾斜会物化到目标端存储。"
        ),
        "spk_recheck_improved": (
            "🔁 复测对比：上次体检（{ts}，key=`{pk}`，判定 {pv}）→ 本次判定 "
            "{cv} —— ✅ 分片键问题已解决，闭环完成。"
        ),
        "spk_recheck_regressed": (
            "🔁 复测对比：上次体检（{ts}，key=`{pk}`，判定 {pv}）→ 本次判定 "
            "{cv} —— ⚠️ 出现退化：该键此前实测正常，请排查数据分布变化。"
        ),
        "spk_recheck_still_bad": (
            "🔁 复测对比：上次体检（{ts}，key=`{pk}`，判定 {pv}）→ 本次判定 "
            "{cv} —— ⚠️ 仍未解决：请按候选列修改 partition_column 后再次体检。"
        ),
        "spk_apply_fail": "❌ 无法在配置文本中定位写入点，未做任何修改。",
        "spk_apply_done": (
            "✅ 已把分片键写回配置：{opt} = \"{col}\"（原文件备份为 {bak}）。"
            "请重新体检验证。"
        ),
        "spk_apply_none": (
            "ℹ️ 没有可写回的推荐分片键：未实测到 good/suspect 的键，"
            "或现配置已是最优。"
        ),
        "dsk_conn_handoff": (
            "🔗 已带入数据比对页 B 侧连接（{ds} {host}:{port}/{db}）——"
            "请补密码后点连接。"
        ),
        "dsk_conn_handoff_unsupported": (
            "⚠️ 数据比对页带入的数据源类型（{t}）不支持在此实测——"
            "请手动选择支持的类型。"
        ),
        # --- consistency measurement ---
        "cst_btn": "一致性实测（运行两版 SQL）",
        "cst_running": "正在运行原 SQL 与优化后 SQL 进行对比…",
        "cst_need_opt": "⚠️ 请先在 LLM 模式下生成优化后 SQL。",
        "cst_section": "## 一致性实测（原 SQL vs 优化 SQL）",
        "cst_not_single": (
            "仅支持单条 SELECT / WITH 查询的实测对比——脚本包含多条语句或写操作，"
            "未执行。"
        ),
        "cst_error": "❌ 实测失败：{err}",
        "cst_mismatch": "⛔ 行数不一致：原 {a} 行 vs 优化后 {b} 行——请人工复核改写。",
        "cst_match_full": "✅ 行数一致，且全部 {n} 行结果完全一致。",
        "cst_rows_differ": "⛔ 行数一致但结果内容存在差异——请人工复核改写。",
        "cst_match_count": "✅ 行数一致（结果集较大，未逐行比对）。",
        "cst_agg_match": "✅ 行数一致，且 {n} 个同名列的 COUNT / COUNT DISTINCT / MIN / MAX 逐列一致（结果集较大，未逐行比对）。",
        "cst_agg_differ": "⛔ 行数一致但 {n} 个同名列的逐列聚合值存在差异——请人工复核改写。",
        "cst_col_metric": "指标",
        "cst_col_orig": "原 SQL",
        "cst_col_opt": "优化后 SQL",
        "cst_rows": "返回行数",
        "cst_elapsed": "耗时",
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
