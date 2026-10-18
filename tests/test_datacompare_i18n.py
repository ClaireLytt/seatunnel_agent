"""i18n parity for the React /datacompare workspace (ticket 10).

Checks frontend/datacompare/src/i18n.ts:

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files (plus the labelKey
  tables consumed via t(labelKey)) is defined;
- keys ported from the legacy Gradio page carry the DC_I18N wording
  verbatim (expected values live INLINE below, copied from
  src/seatunnel_agent/agents/data/data_comparison/i18n.py so the React
  side stays pinned even after ticket 11 prunes the Python dict).

Keys with no legacy wording to check (new UI text on the React page):
- subtitle, results, home: page chrome with no legacy counterpart
  (legacy dc_title was a bare markdown header).
- title: legacy dc_title is "### Data Comparison" — the "### " is
  Gradio markdown syntax, not wording; the React h1 drops it.
- connecting: busy state of the connect button (legacy had none).
- options, reports: accordion titles — the legacy blocks had no label
  key (plain layout groups).
- reportRefresh: the legacy dropdown refreshed implicitly on change.
- genSyncDownload: the legacy DownloadButton was unlabeled ("⬇" file
  glyph); React keeps the glyph plus a short caption.
- scheduleActive/scheduleInactive/scheduleLastRun/scheduleLastError:
  the legacy status came server-rendered (dc_schedule_running/stopped
  stay in Python); the React card shows live GET /schedule/status.
- trendDelta: the legacy matplotlib ylabel was hardcoded English
  "Row Count Delta" in both locales (ui.py set_ylabel literal).
- delete: aria-label for the 🗑 glyph buttons (legacy buttons were
  bare glyphs with no accessible name).

Backend-rendered keys (124 card/report keys + guard messages like
dc_connect_both / dc_where_invalid) stay in Python DC_I18N and reach
the page already localized inside result HTML — they are deliberately
NOT in i18n.ts (inventory: st-migration-notes/datacompare/i18n-inventory.md).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "datacompare" / "src"
I18N_TS = SRC / "i18n.ts"

# React key -> {en, zh} legacy wording, verbatim from DC_I18N
# (src/.../data_comparison/i18n.py). Comment = legacy dc_* key when the
# React name differs.
LEGACY_EXPECTED: dict[str, dict[str, str]] = {
    "sourceA": {"en": "Source A", "zh": "数据源 A"},  # dc_source_a
    "sourceB": {"en": "Source B", "zh": "数据源 B"},  # dc_source_b
    "dsType": {"en": "Data Source", "zh": "数据源类型"},  # dc_datasource_type
    "host": {"en": "Host", "zh": "主机地址"},
    "port": {"en": "Port", "zh": "端口"},
    "database": {"en": "Database", "zh": "数据库"},
    "username": {"en": "Username", "zh": "用户名"},
    "password": {"en": "Password", "zh": "密码"},
    "connect": {"en": "Connect", "zh": "连接"},
    "selectTable": {"en": "Select Table", "zh": "选择表"},
    "actionSchema": {"en": "Schema Diff", "zh": "结构对比"},  # dc_compare_schema
    "actionCount": {"en": "Row Count", "zh": "行数对比"},  # dc_compare_count
    "actionSample": {"en": "Sample Data", "zh": "样本数据"},  # dc_compare_sample
    "actionAggregate": {"en": "Aggregates", "zh": "聚合对比"},  # dc_compare_agg
    "actionCompareAll": {"en": "Compare All", "zh": "全部对比"},  # dc_compare_all
    "actionProfile": {"en": "Column Profile", "zh": "字段画像"},  # dc_profile
    "actionBatchCount": {"en": "Batch Count", "zh": "批量行数"},  # dc_batch_count
    "actionBatchFull": {"en": "Batch Full Compare", "zh": "批量全量对比"},  # dc_batch_full
    "running": {"en": "Comparing...", "zh": "比对中..."},  # dc_running
    # dc_placeholder (empty results panel)
    "resultsEmpty": {"en": "Connect two data sources and click Compare",
                     "zh": "请连接两个数据源并点击对比"},
    "where": {"en": "WHERE", "zh": "WHERE 条件"},  # dc_where_clause
    "whereHint": {"en": "e.g. date > '2024-01-01'", "zh": "例如 date > '2024-01-01'"},
    "threshold": {"en": "Threshold", "zh": "阈值"},
    "thresholdHint": {"en": "e.g. 5% or 100", "zh": "例如 5% 或 100"},
    "keyColumns": {"en": "Key Column(s)", "zh": "主键列"},  # dc_key_columns
    "colMapping": {"en": "Column Mapping", "zh": "字段映射"},  # dc_col_mapping
    "colMappingHint": {"en": "e.g. col_a:col_b, name:full_name",
                       "zh": "例如 col_a:col_b, name:full_name"},
    "sampleStrategy": {"en": "Sampling", "zh": "采样方式"},  # dc_sample_strategy
    "stratifiedCol": {"en": "Group Column", "zh": "分组列"},
    "stratifiedColHint": {"en": "Column to stratify by (e.g. region, category)",
                          "zh": "按此列分层采样（如 region、category）"},
    "masking": {"en": "Enable masking", "zh": "启用脱敏"},  # dc_masking_enabled
    "resetOptions": {"en": "Reset Options", "zh": "重置选项"},
    "presets": {"en": "Presets", "zh": "预设"},
    "presetName": {"en": "Preset Name", "zh": "预设名称"},
    "presetEnv": {"en": "Environment", "zh": "环境"},  # dc_preset_env
    "presetSave": {"en": "Save Preset", "zh": "保存预设"},
    "presetLoad": {"en": "Load Preset", "zh": "加载预设"},
    "presetSaved": {"en": "Preset saved", "zh": "预设已保存"},
    "presetDeleted": {"en": "Preset deleted", "zh": "预设已删除"},
    "presetNoPresets": {"en": "No saved presets", "zh": "无已保存预设"},
    "incremental": {"en": "Incremental", "zh": "增量对比"},
    "watermarkCol": {"en": "Watermark Column", "zh": "水位线列"},
    "watermarkColHint": {"en": "e.g. updated_at", "zh": "例如 updated_at"},  # dc_watermark_hint
    "watermarkVal": {"en": "Last Value", "zh": "上次值"},  # dc_watermark_value
    "incrementalRun": {"en": "Incremental Compare", "zh": "增量对比"},  # dc_incremental_compare
    "quality": {"en": "Quality Rules", "zh": "质量规则"},  # dc_quality
    "qualityRules": {"en": "Rules", "zh": "规则"},
    "qualityRulesHint": {"en": "e.g. name:not_null>95, age:range:0-150",
                         "zh": "例如 name:not_null>95, age:range:0-150"},
    "qualityRun": {"en": "Check Quality", "zh": "质量检查"},  # dc_quality_check
    "skew": {"en": "Data Skew", "zh": "数据倾斜"},
    "skewCols": {"en": "Skew Column", "zh": "倾斜分析列"},  # dc_skew_column
    "skewColsHint": {"en": "Comma-separated columns to analyze",
                     "zh": "逗号分隔的列名"},  # dc_skew_columns_hint
    "skewRun": {"en": "Analyze Skew", "zh": "分析倾斜"},  # dc_skew_analyze
    "checksum": {"en": "Checksum", "zh": "校验和"},
    "checksumColsHint": {"en": "Comma-separated columns for checksum",
                         "zh": "逗号分隔的校验列"},  # dc_checksum_columns_hint
    "checksumRun": {"en": "Compare Checksum", "zh": "校验和对比"},  # dc_checksum_analyze
    "chunkedRun": {"en": "Chunked Verify", "zh": "分块校验"},  # dc_chunked_btn
    "partition": {"en": "Partition", "zh": "分区比对"},
    "partitionCol": {"en": "Partition Column", "zh": "分区列"},
    "partitionColHint": {"en": "Column to partition by", "zh": "按此列分区统计"},
    "partitionRun": {"en": "Compare Partitions", "zh": "对比分区"},  # dc_partition_analyze
    "customAgg": {"en": "Custom Aggregates", "zh": "自定义聚合"},
    "customAggHint": {"en": "One per line: alias=EXPRESSION", "zh": "每行一个：别名=表达式"},
    "customAggRun": {"en": "Compare Custom Agg", "zh": "比对自定义聚合"},  # dc_custom_agg_analyze
    "customSql": {"en": "Custom SQL", "zh": "自定义 SQL"},
    "sqlPlaceholder": {"en": "SELECT * FROM ...", "zh": "SELECT * FROM ..."},
    "sqlRun": {"en": "Compare SQL", "zh": "SQL 对比"},  # dc_compare_sql
    "genSync": {"en": "Generate Sync Config", "zh": "生成同步配置"},
    "genDiffSql": {"en": "Generate Diff SQL", "zh": "生成差异 SQL"},
    "lineageTitle": {"en": "Upstream Dependencies", "zh": "上游依赖"},
    "lineageHint": {"en": "SQL statements to trace lineage from (one per line)",
                    "zh": "用于溯源的SQL语句（每行一条）"},
    "envTitle": {"en": "Environment", "zh": "环境"},  # dc_environment
    "envA": {"en": "Env A", "zh": "环境 A"},
    "envB": {"en": "Env B", "zh": "环境 B"},
    "envHint": {"en": "e.g. dev, staging, prod", "zh": "例如 dev, staging, prod"},
    "compareEnvs": {"en": "Compare Environments", "zh": "跨环境对比"},
    "templates": {"en": "Templates", "zh": "模板"},
    "templateName": {"en": "Template Name", "zh": "模板名称"},
    "templateSave": {"en": "Save Template", "zh": "保存模板"},
    "templateLoad": {"en": "Load Template", "zh": "加载模板"},
    "templateSaved": {"en": "Template saved", "zh": "模板已保存"},
    "templateDeleted": {"en": "Template deleted", "zh": "模板已删除"},
    "templateNoTemplates": {"en": "No saved templates", "zh": "无已保存模板"},
    "batchTemplates": {"en": "Batch Templates", "zh": "批量模板"},
    "batchTemplatesRun": {"en": "Run Selected", "zh": "运行选中"},
    "reportSave": {"en": "Save Report", "zh": "保存报告"},  # dc_save_report
    "reportLoad": {"en": "Load Report", "zh": "加载报告"},  # dc_load_report
    "reportSaved": {"en": "Report saved", "zh": "报告已保存"},  # dc_saved
    "reportNoReport": {"en": "No report yet — run a comparison first",
                       "zh": "暂无报告 — 请先执行对比"},  # dc_no_report
    "reportNoReports": {"en": "No saved reports", "zh": "无已保存报告"},  # dc_no_reports
    "reportDiff": {"en": "Report Diff", "zh": "报告对比"},  # dc_report_diff
    "reportOld": {"en": "Old Report", "zh": "旧报告"},
    "reportNew": {"en": "New Report", "zh": "新报告"},
    "exportCsv": {"en": "Export CSV", "zh": "导出 CSV"},
    "exportExcel": {"en": "Export Excel", "zh": "导出 Excel"},
    "viewReport": {"en": "View Report", "zh": "查看报告"},
    "schedule": {"en": "Schedule", "zh": "定时任务"},
    "scheduleInterval": {"en": "Interval (min)", "zh": "间隔（分钟）"},
    "scheduleStart": {"en": "Start Schedule", "zh": "启动定时"},
    "scheduleStop": {"en": "Stop Schedule", "zh": "停止定时"},
    "webhook": {"en": "Webhook", "zh": "Webhook 通知"},
    "webhookUrl": {"en": "Webhook URL", "zh": "Webhook URL"},
    "webhookUrlHint": {"en": "https://example.com/webhook",
                       "zh": "https://example.com/webhook"},
    "webhookOnFail": {"en": "Notify on failure only", "zh": "仅失败时通知"},
    "trends": {"en": "Trends", "zh": "趋势"},  # dc_trend
    "alertRules": {"en": "Alert Rules", "zh": "告警规则"},
    "alertRulesHint": {
        "en": "metric>threshold:consecutive (e.g. delta>100:3, skew_top1>50:2, "
              "skew_top1_jump>10:1)",
        "zh": "指标>阈值:连续次数（如 delta>100:3、skew_top1>50:2、skew_top1_jump>10:1）",
    },
    "trendShow": {"en": "Comparison Trends", "zh": "对比趋势"},  # dc_trend_chart (button)
    "trendNoData": {"en": "No historical data for trends", "zh": "无历史数据可用于趋势分析"},
    # dc_history_count: {n} → i18next {{n}}
    "trendRecords": {"en": "{{n}} comparison records", "zh": "{{n}} 条对比记录"},
    "trendMismatches": {"en": "Aggregate Mismatches", "zh": "聚合不一致数"},  # dc_trend_mismatches
    "trendSchema": {"en": "Schema Changes", "zh": "结构变更数"},  # dc_trend_schema
    "trendSkew": {"en": "Skew Top-1 % (worst column)",
                  "zh": "倾斜 Top-1 占比（最差列）"},  # dc_trend_skew
}


def _parse_locale(block: str) -> dict[str, str]:
    pairs = re.findall(r"(\w+):\s*'((?:[^'\\]|\\.)*)'|(\w+):\s*\"((?:[^\"\\]|\\.)*)\"",
                       block)
    out: dict[str, str] = {}
    for k1, v1, k2, v2 in pairs:
        key, val = (k1, v1) if k1 else (k2, v2)
        out[key] = (val.replace("\\'", "'").replace('\\"', '"')
                    .replace("\\n", "\n"))
    return out


def _resources() -> dict[str, dict[str, str]]:
    text = I18N_TS.read_text(encoding="utf-8")
    locales = re.findall(
        r"^  (en|zh): \{\s*translation: \{(.*?)^    \},\s*^  \},",
        text,
        re.S | re.M,
    )
    assert {name for name, _ in locales} == {"en", "zh"}, "en/zh blocks not found"
    return {name: _parse_locale(body) for name, body in locales}


def _workspace_sources() -> list[str]:
    files = list(SRC.glob("*.tsx")) + list((SRC / "components").glob("*.tsx"))
    assert files, "no .tsx files found — glob broken?"
    return [f.read_text(encoding="utf-8") for f in files]


def test_en_zh_key_sets_match() -> None:
    res = _resources()
    assert res["en"], "no keys parsed from i18n.ts"
    assert set(res["en"]) == set(res["zh"])


def test_every_t_usage_is_defined() -> None:
    keys = set(_resources()["en"])
    used: set[str] = set()
    for text in _workspace_sources():
        used |= set(re.findall(r"\bt\('(\w+)'", text))
        # action tables rendered via t(labelKey)
        used |= set(re.findall(r"labelKey: '(\w+)'", text))
    assert used, "no t() usages found — glob broken?"
    missing = used - keys
    assert not missing, f"t() keys missing from i18n.ts: {sorted(missing)}"


def test_ported_keys_match_legacy_verbatim() -> None:
    res = _resources()
    problems: list[str] = []
    for react_key, expected_by_lang in LEGACY_EXPECTED.items():
        for lang in ("en", "zh"):
            got = res[lang].get(react_key)
            if got != expected_by_lang[lang]:
                problems.append(
                    f"{lang}.{react_key}: {got!r} != legacy {expected_by_lang[lang]!r}")
    assert not problems, "\n".join(problems)


def test_delete_glyph_buttons_have_localized_aria() -> None:
    """The 🗑 preset/template delete buttons keep the legacy bare glyph
    but carry a localized accessible name."""
    for comp in ("PresetsCard.tsx", "TemplatesCard.tsx"):
        text = (SRC / "components" / comp).read_text(encoding="utf-8")
        assert re.search(r"aria-label=\{t\('delete'\)\}", text), (
            f"{comp}: delete button must use aria-label={{t('delete')}}")


def test_i18n_initialized_from_lang_cookie() -> None:
    text = I18N_TS.read_text(encoding="utf-8")
    assert "langFromCookie" in text
    assert re.search(r"lng:\s*langFromCookie\(\)", text)
