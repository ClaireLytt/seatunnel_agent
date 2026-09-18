# -*- coding: utf-8 -*-
"""Tests for the SQL Code Review module (linter, report, tools)."""

from __future__ import annotations

import json

import pytest

from seatunnel_agent.sql_review.linter import (
    clean_sql,
    is_known_dialect,
    lint_sql,
    line_of,
    normalize_dialect,
)
from seatunnel_agent.sql_review.report import (
    CHECK_CATALOG,
    Finding,
    ReviewReport,
    Severity,
    render_report,
)
from seatunnel_agent.sql_review.tools import (
    SQLReviewRuntime,
    execute_review_tool,
)
from seatunnel_agent.sql_review.agent import static_review


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def categories(findings):
    return {f.category for f in findings}


def by_category(findings, cat):
    return [f for f in findings if f.category == cat]


# ---------------------------------------------------------------------------
# clean_sql / dialect
# ---------------------------------------------------------------------------

def test_clean_sql_preserves_length_and_newlines():
    sql = "select 'a--b' -- comment\nfrom t /* block\ncomment */ where x=1"
    cleaned = clean_sql(sql)
    assert len(cleaned) == len(sql)
    assert cleaned.count("\n") == sql.count("\n")
    assert "comment" not in cleaned
    assert "a--b" not in cleaned


def test_line_of():
    sql = "a\nb\nc"
    assert line_of(sql, 0) == 1
    assert line_of(sql, 2) == 2
    assert line_of(sql, 4) == 3


@pytest.mark.parametrize("raw,expected", [
    ("hive", "hive"),
    ("Spark SQL", "spark"),
    ("FlinkSQL", "flink"),
    ("odps", "maxcompute"),
    ("MaxCompute", "maxcompute"),
    ("", "hive"),
    ("mysql", "hive"),
])
def test_normalize_dialect(raw, expected):
    assert normalize_dialect(raw) == expected


# ---------------------------------------------------------------------------
# Linter rules
# ---------------------------------------------------------------------------

SPEC_EXAMPLE = """select level1_category_name
          ,level1_category_code
          ,count(1)
from zz.dwm_scm_detail_di
group by level1_category_name"""


def test_groupby_missing_column_is_critical():
    findings = lint_sql(SPEC_EXAMPLE, "hive")
    gb = by_category(findings, "groupby_completeness")
    assert len(gb) == 1
    assert gb[0].severity == Severity.CRITICAL
    assert "level1_category_code" in gb[0].description


def test_groupby_complete_passes():
    sql = """select level1_category_name, level1_category_code, count(1)
from zz.dwm_scm_detail_di
where pt = '20260313'
group by level1_category_name, level1_category_code"""
    assert not by_category(lint_sql(sql), "groupby_completeness")


def test_groupby_aggregates_and_window_ignored():
    sql = """select uid, sum(amt), row_number() over (partition by uid order by dt) as rn
from t where pt='20260101' group by uid"""
    assert not by_category(lint_sql(sql), "groupby_completeness")


def test_groupby_positional_skipped():
    sql = "select uid, dt, count(1) from t where pt='1' group by 1, 2"
    assert not by_category(lint_sql(sql), "groupby_completeness")


def test_groupby_subquery_checked_independently():
    sql = """select uid, cnt from (
    select uid, dt, count(1) as cnt from t where pt='1' group by uid
) x"""
    gb = by_category(lint_sql(sql), "groupby_completeness")
    assert len(gb) == 1
    assert "dt" in gb[0].description


def test_join_without_on_is_critical():
    sql = "select * from a join b where a.pt='1'"
    js = by_category(lint_sql(sql), "join_cartesian")
    assert js and js[0].severity == Severity.CRITICAL


def test_join_with_on_passes():
    sql = "select a.x from a join b on a.id = b.id where a.pt='1'"
    assert not by_category(lint_sql(sql), "join_cartesian")


def test_cross_join_is_risk():
    sql = "select a.x from a cross join b where a.pt='1'"
    js = by_category(lint_sql(sql), "join_cartesian")
    assert js and js[0].severity == Severity.RISK


def test_join_on_with_or_flagged():
    sql = "select a.x from a join b on a.id = b.id or a.code = b.code where a.pt='1'"
    assert by_category(lint_sql(sql), "join_condition")


def test_null_equality_is_critical():
    for op in ("=", "!=", "<>"):
        sql = f"select x from t where pt='1' and name {op} null"
        fs = by_category(lint_sql(sql), "where_syntax")
        assert fs and fs[0].severity == Severity.CRITICAL


def test_is_null_passes():
    sql = "select x from t where pt='1' and name is not null"
    assert not by_category(lint_sql(sql), "where_syntax")


def test_division_without_guard_is_risk():
    sql = "select amt / cnt from t where pt='1'"
    fs = by_category(lint_sql(sql), "calculation")
    assert fs and fs[0].severity == Severity.RISK


def test_division_with_nullif_passes():
    sql = "select amt / nullif(cnt, 0) from t where pt='1'"
    assert not by_category(lint_sql(sql), "calculation")


def test_division_by_zero_literal_is_critical():
    sql = "select amt / 0 from t where pt='1'"
    fs = by_category(lint_sql(sql), "calculation")
    assert any(f.severity == Severity.CRITICAL for f in fs)


def test_missing_partition_filter_on_suffix_table():
    sql = "select x from zz.dwd_order_di"
    fs = by_category(lint_sql(sql, "hive"), "partition_pruning")
    assert fs and "dwd_order_di" in fs[0].description


def test_partition_filter_present_passes():
    sql = "select x from zz.dwd_order_di where pt = '20260313'"
    assert not by_category(lint_sql(sql, "hive"), "partition_pruning")


def test_partition_rules_skipped_for_flink():
    sql = "select x from zz.dwd_order_di"
    assert not by_category(lint_sql(sql, "flink"), "partition_pruning")


def test_unquoted_partition_value_is_risk():
    sql = "select x from t_di where pt = 20260313"
    fs = by_category(lint_sql(sql), "where_partition")
    assert fs and "20260313" in fs[0].description


def test_select_star_is_risk():
    sql = "select * from t where pt='1'"
    assert by_category(lint_sql(sql), "resource_usage")


def test_count_star_not_flagged_as_select_star():
    sql = "select count(*) from t where pt='1'"
    fs = [f for f in lint_sql(sql) if "SELECT *" in f.description]
    assert not fs


def test_order_by_without_limit_is_risk():
    sql = "select x from t where pt='1' order by x"
    fs = [f for f in lint_sql(sql, "hive") if "ORDER BY" in f.description]
    assert fs and fs[0].severity == Severity.RISK


def test_order_by_with_limit_passes():
    sql = "select x from t where pt='1' order by x limit 100"
    assert not [f for f in lint_sql(sql, "hive") if "ORDER BY" in f.description]


def test_union_without_all_is_suggestion():
    sql = "select x from a where pt='1' union select x from b where pt='1'"
    fs = [f for f in lint_sql(sql) if "UNION" in f.description]
    assert fs and fs[0].severity == Severity.SUGGESTION


def test_union_all_passes():
    sql = "select x from a where pt='1' union all select x from b where pt='1'"
    assert not [f for f in lint_sql(sql) if "UNION" in f.description and "UNION ALL" not in f.description]


def test_count_distinct_is_suggestion():
    sql = "select count(distinct uid) from t where pt='1'"
    fs = by_category(lint_sql(sql), "data_skew")
    assert fs and fs[0].severity == Severity.SUGGESTION


def test_insert_overwrite_without_partition_is_risk():
    sql = "insert overwrite table dw.t_target select x from t where pt='1'"
    fs = by_category(lint_sql(sql, "hive"), "where_partition")
    assert fs and "PARTITION" in fs[0].description


def test_insert_overwrite_with_partition_passes():
    sql = "insert overwrite table dw.t_target partition (pt='${bizdate}') select x from t where pt='1'"
    assert not by_category(lint_sql(sql, "hive"), "where_partition")


def test_distinct_with_groupby_is_suggestion():
    sql = "select distinct uid from t where pt='1' group by uid"
    assert by_category(lint_sql(sql), "dedup")


def test_long_sql_without_comments_readability():
    sql = "\n".join(["select x"] + [f",col_{i}" for i in range(20)] + ["from t where pt='1'"])
    assert by_category(lint_sql(sql), "readability")


def test_comments_and_literals_not_linted():
    sql = "-- select * from bad_table\nselect x from t where pt='1' and note = 'a = null'"
    findings = lint_sql(sql)
    assert not by_category(findings, "where_syntax")
    assert not [f for f in findings if "SELECT *" in f.description]


def test_clean_sql_passes_clean_query():
    sql = """select uid, count(1) as cnt
from dw.t_order_di
where pt = '${bizdate}' and uid is not null
group by uid"""
    findings = lint_sql(sql, "hive")
    assert not [f for f in findings if f.severity == Severity.CRITICAL]


def test_findings_sorted_by_severity():
    sql = "select * from t_di where a != null order by x"
    sev = [f.severity for f in lint_sql(sql)]
    assert sev == sorted(sev, key=lambda s: {Severity.CRITICAL: 0, Severity.RISK: 1, Severity.SUGGESTION: 2}[s])


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def test_render_report_sections_present():
    report = ReviewReport(findings=lint_sql(SPEC_EXAMPLE), summary="测试总结")
    md = render_report(report)
    for section in ("## CR 报告", "🔴 严重问题", "🟡 潜在风险", "🟢 优化建议",
                    "📊 检查统计", "💡 总体评价"):
        assert section in md
    assert "测试总结" in md
    assert "GROUP BY 缺少 level1_category_code" in md


def test_render_report_empty_findings():
    md = render_report(ReviewReport(findings=[]))
    assert "无" in md
    assert f"检查项总数：{len(CHECK_CATALOG)}" in md
    assert f"通过：{len(CHECK_CATALOG)}" in md
    assert "代码检查通过" in md


def test_stats_counting():
    findings = [
        Finding(Severity.CRITICAL, "groupby_completeness", "d", "行 1", "i", "s"),
        Finding(Severity.RISK, "partition_pruning", "d", "行 2", "i", "s"),
        Finding(Severity.RISK, "partition_pruning", "d", "行 3", "i", "s"),
        Finding(Severity.SUGGESTION, "readability", "d", "全局", "i", "s"),
    ]
    stats = ReviewReport(findings=findings).stats()
    assert stats["total"] == len(CHECK_CATALOG)
    assert stats["problems"] == 1
    assert stats["risks"] == 2
    # suggestions don't fail a category; 2 categories flagged
    assert stats["passed"] == len(CHECK_CATALOG) - 2


def test_table_cells_escaped():
    findings = [Finding(Severity.CRITICAL, "calculation", "a|b\nc", "行 1", "i", "s")]
    md = render_report(ReviewReport(findings=findings))
    assert "a\\|b c" in md


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def test_tool_lint_sql():
    rt = SQLReviewRuntime(sql=SPEC_EXAMPLE, dialect="hive")
    out = json.loads(execute_review_tool("lint_sql", {}, rt))
    assert out["success"] and out["finding_count"] >= 2
    assert rt.lint_findings


def test_tool_get_table_schema_without_store():
    rt = SQLReviewRuntime(sql="select 1", dialect="hive")
    out = json.loads(execute_review_tool("get_table_schema", {"table": "t"}, rt))
    assert "error" in out


def test_tool_submit_review_merges_and_dedupes():
    rt = SQLReviewRuntime(sql=SPEC_EXAMPLE, dialect="hive")
    execute_review_tool("lint_sql", {}, rt)
    lint_gb = [f for f in rt.lint_findings if f.category == "groupby_completeness"][0]
    out = json.loads(execute_review_tool("submit_review", {
        "findings": [
            {  # duplicate of a linter finding -> dropped
                "severity": "critical",
                "category": "groupby_completeness",
                "description": "duplicate",
                "location": lint_gb.location,
            },
            {  # new LLM finding -> kept
                "severity": "suggestion",
                "category": "readability",
                "description": "建议添加表别名注释",
                "location": "全局",
                "suggestion": "加注释",
            },
            {  # invalid severity -> dropped
                "severity": "fatal",
                "category": "calculation",
                "description": "x",
                "location": "行 1",
            },
        ],
        "summary": "总体评价文本",
    }, rt))
    assert out["success"]
    assert "总体评价文本" in out["report"]
    assert "duplicate" not in out["report"]
    assert "建议添加表别名注释" in out["report"]
    assert rt.report is not None


def test_tool_submit_review_runs_lint_if_not_called():
    rt = SQLReviewRuntime(sql=SPEC_EXAMPLE, dialect="hive")
    out = json.loads(execute_review_tool("submit_review", {"findings": [], "summary": "s"}, rt))
    assert out["success"]
    assert "GROUP BY 缺少 level1_category_code" in out["report"]


def test_tool_unknown():
    rt = SQLReviewRuntime(sql="select 1", dialect="hive")
    out = json.loads(execute_review_tool("nope", {}, rt))
    assert "error" in out


def test_unknown_llm_category_mapped_to_readability():
    rt = SQLReviewRuntime(sql="select 1", dialect="hive")
    out = json.loads(execute_review_tool("submit_review", {
        "findings": [{
            "severity": "risk",
            "category": "made_up_category",
            "description": "某发现",
            "location": "行 1",
        }],
        "summary": "s",
    }, rt))
    assert out["success"]
    assert "某发现" in out["report"]


# ---------------------------------------------------------------------------
# Regressions: depth-aware scanning, alias/keyword handling
# ---------------------------------------------------------------------------

def _cats(findings, cat):
    return [f for f in findings if f.category == cat]


def test_join_subquery_with_on_not_cartesian():
    sql = ("select a.x from a join (select id from b where pt='1') t "
           "on a.id = t.id where a.pt='1'")
    assert not _cats(lint_sql(sql, "hive"), "join_cartesian")


def test_join_in_subquery_without_on_still_flagged():
    sql = "select t.x from (select a.x from a join b) t where t.pt='1'"
    found = _cats(lint_sql(sql, "hive"), "join_cartesian")
    assert found and found[0].severity == Severity.CRITICAL


def test_join_on_not_borrowed_across_scopes():
    # inner join has no ON; outer join's ON must not satisfy it
    sql = ("select t.x from (select a.x, a.id from a join b) t "
           "join c on t.id = c.id where t.pt='1'")
    assert _cats(lint_sql(sql, "hive"), "join_cartesian")


def test_groupby_suffix_columns_not_confused():
    sql = ("select category_code, code, count(1) from t "
           "where pt='1' group by category_code")
    found = _cats(lint_sql(sql, "hive"), "groupby_completeness")
    assert found and "code" in found[0].description


def test_groupby_qualified_vs_bare_column_covered():
    sql = "select t.uid, count(1) from t where pt='1' group by uid"
    assert not _cats(lint_sql(sql, "hive"), "groupby_completeness")


def test_select_distinct_not_treated_as_column():
    sql = "select distinct uid from t where pt='1' group by uid"
    assert not _cats(lint_sql(sql, "hive"), "groupby_completeness")


def test_group_by_select_alias_covered():
    sql = ("select substr(dt,1,6) as month, count(1) from t "
           "where pt='1' group by month")
    assert not _cats(lint_sql(sql, "maxcompute"), "groupby_completeness")


def test_group_by_cube_skipped():
    sql = "select a, b, count(1) from t where pt='1' group by cube(a, b)"
    assert not _cats(lint_sql(sql, "hive"), "groupby_completeness")


def test_division_with_case_zero_guard_not_flagged():
    sql = "select case when cnt = 0 then 0 else amt / cnt end from t where pt='1'"
    assert not _cats(lint_sql(sql, "hive"), "calculation")


def test_division_by_keyword_not_flagged():
    sql = "select case when a > 1 then x else y end / nullif(z, 0) from t where pt='1'"
    assert not _cats(lint_sql(sql, "hive"), "calculation")


def test_unguarded_division_still_flagged():
    sql = "select amt / cnt from t where pt='1'"
    assert _cats(lint_sql(sql, "hive"), "calculation")


def test_cte_name_not_flagged_as_unpartitioned_table():
    sql = ("with tmp_di as (select id from src group by id) "
           "select id from tmp_di group by id")
    assert not _cats(lint_sql(sql, "hive"), "partition_pruning")


def test_partition_finding_deduped_per_table():
    sql = ("select a.id from ods_x_di a join ods_x_di b on a.id = b.id "
           "join ods_x_di c on a.id = c.id")
    found = _cats(lint_sql(sql, "hive"), "partition_pruning")
    assert len(found) == 1


def test_order_by_limit_in_other_statement_not_counted():
    sql = ("select id from t where pt='1' order by id;\n"
           "select id from u where pt='1' limit 10")
    found = [f for f in lint_sql(sql, "hive") if "ORDER BY" in f.description]
    assert found


def test_qualified_partition_filter_covers_only_its_table():
    sql = ("select a.id from ods_a_di a join ods_b_di b on a.id = b.id "
           "where a.pt = '20260101'")
    found = _cats(lint_sql(sql, "hive"), "partition_pruning")
    assert len(found) == 1
    assert "ods_b_di" in found[0].description


def test_all_tables_qualified_filtered_clean():
    sql = ("select a.id from ods_a_di a join ods_b_di b on a.id = b.id "
           "where a.pt='1' and b.pt='1'")
    assert not _cats(lint_sql(sql, "hive"), "partition_pruning")


def test_bare_partition_filter_suppresses_all():
    sql = "select id from ods_a_di where pt = '20260101' group by id"
    assert not _cats(lint_sql(sql, "hive"), "partition_pruning")


def _type_check_store():
    from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl
    ddl = """
    create table zz.orders_di (
      order_id bigint comment 'id',
      user_id string comment 'uid'
    ) partitioned by (pt string comment '');
    create table zz.users_df (
      user_id bigint comment 'uid',
      name string comment ''
    ) partitioned by (pt string comment '');
    """
    return SchemaStore(parse_ddl(ddl))


def test_join_key_type_mismatch_flagged_with_store():
    sql = ("select o.order_id from zz.orders_di o join zz.users_df u "
           "on o.user_id = u.user_id where o.pt='1' and u.pt='1'")
    found = _cats(lint_sql(sql, "hive", store=_type_check_store()), "join_condition")
    assert found
    assert "类型不一致" in found[0].description
    assert "string" in found[0].description and "bigint" in found[0].description


def test_join_key_same_type_family_clean():
    sql = ("select o.order_id from zz.orders_di o join zz.users_df u "
           "on o.order_id = u.user_id where o.pt='1' and u.pt='1'")
    assert not _cats(lint_sql(sql, "hive", store=_type_check_store()), "join_condition")


def test_join_key_type_check_skipped_without_store():
    sql = ("select o.order_id from zz.orders_di o join zz.users_df u "
           "on o.user_id = u.user_id where o.pt='1' and u.pt='1'")
    assert not _cats(lint_sql(sql, "hive"), "join_condition")


def test_join_key_unknown_table_not_flagged():
    sql = ("select o.id from zz.unknown_di o join zz.users_df u "
           "on o.user_id = u.user_id where o.pt='1' and u.pt='1'")
    assert not _cats(lint_sql(sql, "hive", store=_type_check_store()), "join_condition")


def test_is_known_dialect():
    assert is_known_dialect("hive")
    assert is_known_dialect("ODPS")
    assert is_known_dialect(" Spark SQL ")
    assert not is_known_dialect("mysql")
    assert not is_known_dialect("")


# ---------------------------------------------------------------------------
# static_review (no-LLM entry point)
# ---------------------------------------------------------------------------

def test_static_review_end_to_end():
    md = static_review(SPEC_EXAMPLE, "hive")
    assert "## CR 报告" in md
    assert "GROUP BY 缺少 level1_category_code" in md
    assert "缺少分区过滤条件" in md


# ---------------------------------------------------------------------------
# Regression: bare aliases (no AS) & comma joins
# ---------------------------------------------------------------------------

def test_bare_alias_after_function_grouped_by_alias_clean():
    sql = "select substr(dt,1,6) mon, count(1) from t where pt='1' group by mon"
    assert not _cats(lint_sql(sql, "hive"), "groupby_completeness")


def test_bare_alias_after_case_when_grouped_by_alias_clean():
    sql = ("select case when a=1 then b else c end flag, count(1) "
           "from t where pt='1' group by flag")
    assert not _cats(lint_sql(sql, "hive"), "groupby_completeness")


def test_bare_alias_after_arithmetic_grouped_by_alias_clean():
    sql = "select amt + fee total, count(1) from t where pt='1' group by total"
    assert not _cats(lint_sql(sql, "hive"), "groupby_completeness")


def test_case_when_without_alias_grouped_by_expr_clean():
    sql = ("select case when a=1 then b else c end, count(1) "
           "from t where pt='1' group by case when a=1 then b else c end")
    assert not _cats(lint_sql(sql, "hive"), "groupby_completeness")


def test_comma_join_without_condition_is_cartesian_critical():
    sql = "select a.x, b.y from ta a, tb b where a.pt='1'"
    found = _cats(lint_sql(sql, "hive"), "join_cartesian")
    assert found
    assert found[0].severity is Severity.CRITICAL


def test_comma_join_with_link_only_style_suggestion():
    sql = "select a.x, b.y from ta a, tb b where a.id = b.id and a.pt='1'"
    findings = lint_sql(sql, "hive")
    assert not _cats(findings, "join_cartesian")
    styles = _cats(findings, "join_condition")
    assert styles and styles[0].severity is Severity.SUGGESTION


def test_single_table_from_no_comma_join_finding():
    sql = "select uid, count(1) from t where pt='1' group by uid"
    findings = lint_sql(sql, "hive")
    assert not _cats(findings, "join_cartesian")
    assert not _cats(findings, "join_condition")


# ---------------------------------------------------------------------------
# ReviewConfig / .sqlreview.yaml
# ---------------------------------------------------------------------------

from seatunnel_agent.sql_review.config import (
    DEFAULT_CONFIG,
    ReviewConfig,
    load_review_config,
)


def test_load_config_absent_returns_default(tmp_path):
    cfg = load_review_config(cwd=tmp_path)
    assert cfg is DEFAULT_CONFIG


def test_load_config_explicit_missing_path_raises(tmp_path):
    with pytest.raises(ValueError, match="不存在"):
        load_review_config(path=tmp_path / "nope.yaml")


def test_load_config_full_file(tmp_path):
    f = tmp_path / ".sqlreview.yaml"
    f.write_text(
        "partition_columns: [biz_date, pt]\n"
        "incremental_suffixes: [_di]\n"
        "disable: [readability]\n"
        "severity:\n  resource_usage: suggestion\n"
        "fail_on: critical\n",
        encoding="utf-8",
    )
    cfg = load_review_config(path=f)
    assert cfg.partition_cols == ("biz_date", "pt")
    assert cfg.incremental_suffixes == ("_di",)
    assert cfg.disabled_categories == frozenset({"readability"})
    assert cfg.severity_overrides == {"resource_usage": Severity.SUGGESTION}
    assert cfg.fail_on == "critical"
    assert cfg.source_path == str(f)


def test_load_config_auto_discover(tmp_path):
    (tmp_path / ".sqlreview.yml").write_text("fail_on: risk\n", encoding="utf-8")
    cfg = load_review_config(cwd=tmp_path)
    assert cfg.fail_on == "risk"


def test_load_config_unknown_key_raises(tmp_path):
    f = tmp_path / ".sqlreview.yaml"
    f.write_text("bogus_key: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="未知配置项"):
        load_review_config(path=f)


def test_load_config_unknown_category_raises(tmp_path):
    f = tmp_path / ".sqlreview.yaml"
    f.write_text("disable: [not_a_category]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="未知检查类别"):
        load_review_config(path=f)


def test_load_config_bad_severity_raises(tmp_path):
    f = tmp_path / ".sqlreview.yaml"
    f.write_text("severity:\n  readability: fatal\n", encoding="utf-8")
    with pytest.raises(ValueError, match="级别无效"):
        load_review_config(path=f)


def test_load_config_empty_file_ok(tmp_path):
    f = tmp_path / ".sqlreview.yaml"
    f.write_text("", encoding="utf-8")
    cfg = load_review_config(path=f)
    assert cfg.partition_cols == DEFAULT_CONFIG.partition_cols


def test_lint_with_custom_partition_column():
    # biz_date is not a default partition column: the incremental table t_di
    # looks unfiltered under the default config, filtered under a custom one.
    sql = "select id from t_di where biz_date = '20240101'"
    assert by_category(lint_sql(sql, "hive"), "partition_pruning")
    cfg = ReviewConfig(partition_cols=("biz_date",))
    assert not by_category(lint_sql(sql, "hive", config=cfg), "partition_pruning")


def test_lint_custom_partition_column_quoting():
    sql = "select id from t where biz_date = 20240101"
    assert not by_category(lint_sql(sql, "hive"), "where_partition")
    cfg = ReviewConfig(partition_cols=("biz_date",))
    found = by_category(lint_sql(sql, "hive", config=cfg), "where_partition")
    assert found and "biz_date" in found[0].description


def test_lint_custom_incremental_suffix():
    sql = "select id from t_custom"
    assert not by_category(lint_sql(sql, "hive"), "partition_pruning")
    cfg = ReviewConfig(incremental_suffixes=("_custom",))
    assert by_category(lint_sql(sql, "hive", config=cfg), "partition_pruning")


def test_lint_with_disabled_category():
    sql = "select * from t where pt = '20240101'"
    assert by_category(lint_sql(sql, "hive"), "resource_usage")
    cfg = ReviewConfig(disabled_categories=frozenset({"resource_usage"}))
    assert not by_category(lint_sql(sql, "hive", config=cfg), "resource_usage")


def test_lint_with_severity_override():
    sql = "select * from t where pt = '20240101'"
    cfg = ReviewConfig(severity_overrides={"resource_usage": Severity.CRITICAL})
    found = by_category(lint_sql(sql, "hive", config=cfg), "resource_usage")
    assert found and all(f.severity is Severity.CRITICAL for f in found)


# ---------------------------------------------------------------------------
# Table lineage
# ---------------------------------------------------------------------------

from seatunnel_agent.sql_review.lineage import extract_table_lineage
from seatunnel_agent.sql_review.report import TableLineage


def test_lineage_insert_overwrite():
    sql = ("insert overwrite table dw.ads_x partition (pt='1') "
           "select a.id from ods.t1 a join ods.t2 b on a.id = b.id "
           "where a.pt='1' and b.pt='1'")
    lin = extract_table_lineage(sql)
    assert lin.targets == ["dw.ads_x"]
    assert lin.sources == ["ods.t1", "ods.t2"]


def test_lineage_ctas():
    sql = "create table tmp.res as select id from src.t where pt='1'"
    lin = extract_table_lineage(sql)
    assert lin.targets == ["tmp.res"]
    assert lin.sources == ["src.t"]


def test_lineage_cte_excluded_from_sources():
    sql = ("with base as (select id from ods.t where pt='1') "
           "select * from base")
    lin = extract_table_lineage(sql)
    assert lin.sources == ["ods.t"]
    assert lin.targets == []


def test_lineage_select_only_no_targets():
    lin = extract_table_lineage("select 1 from t where pt='1'")
    assert lin.targets == []
    assert lin.sources == ["t"]
    assert bool(lin)


def test_lineage_empty_is_falsy():
    assert not TableLineage()


def test_report_renders_lineage_section():
    rep = ReviewReport(
        findings=[], dialect="hive",
        lineage=TableLineage(sources=["ods.a"], targets=["dw.b"]),
    )
    md = render_report(rep)
    assert "🔗 表级血缘" in md
    assert "来源表：ods.a" in md
    assert "目标表：dw.b" in md


def test_report_without_lineage_no_section():
    md = render_report(ReviewReport(findings=[], dialect="hive"))
    assert "表级血缘" not in md


def test_static_review_report_includes_lineage():
    from seatunnel_agent.sql_review.agent import static_review_report
    rep = static_review_report(
        "insert into dw.x select id from ods.y where pt='1'", "hive")
    assert rep.lineage and rep.lineage.targets == ["dw.x"]


# ---------------------------------------------------------------------------
# runner: collect_sql_files / severity_reached
# ---------------------------------------------------------------------------

from seatunnel_agent.sql_review.runner import collect_sql_files, severity_reached


def test_collect_sql_files_recursive_sorted(tmp_path):
    (tmp_path / "b.sql").write_text("select 1", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.sql").write_text("select 2", encoding="utf-8")
    (tmp_path / "note.txt").write_text("x", encoding="utf-8")
    files = collect_sql_files(tmp_path)
    assert [f.name for f in files] == ["b.sql", "a.sql"]


def _mk_finding(sev):
    return Finding(category="readability", severity=sev, description="d",
                   location="行 1", impact="i", suggestion="s")


def test_severity_reached_thresholds():
    crit = [_mk_finding(Severity.CRITICAL)]
    risk = [_mk_finding(Severity.RISK)]
    sugg = [_mk_finding(Severity.SUGGESTION)]
    assert severity_reached(crit, "critical")
    assert not severity_reached(risk, "critical")
    assert severity_reached(risk, "risk")
    assert severity_reached(crit, "risk")
    assert not severity_reached(sugg, "risk")
    assert severity_reached(sugg, "suggestion")
    assert not severity_reached([], "suggestion")


# ---------------------------------------------------------------------------
# ReviewLogger (jsonl history)
# ---------------------------------------------------------------------------

from seatunnel_agent.sql_review.rlog import ReviewLogger


def test_review_logger_log_and_recent(tmp_path):
    logger = ReviewLogger(log_dir=tmp_path)
    logger.log(
        sql="select * from t", dialect="hive", mode="static",
        findings=[_mk_finding(Severity.RISK)], stats={"risk": 1},
        target="a.sql", elapsed_ms=5,
    )
    recs = logger.recent()
    assert len(recs) == 1
    r = recs[0]
    assert r["dialect"] == "hive"
    assert r["mode"] == "static"
    assert r["target"] == "a.sql"
    assert r["categories"] == ["readability"]
    assert r["severities"] == {"risk": 1}
    assert r["elapsed_ms"] == 5


def test_review_logger_summarize(tmp_path):
    logger = ReviewLogger(log_dir=tmp_path)
    logger.log("s1", "hive", "static",
               [_mk_finding(Severity.CRITICAL), _mk_finding(Severity.RISK)])
    logger.log("s2", "spark", "agent", [_mk_finding(Severity.RISK)])
    s = logger.summarize()
    assert s["reviews"] == 2
    assert s["findings"] == 3
    assert s["severities"] == {"critical": 1, "risk": 2}
    assert s["top_categories"][0]["category"] == "readability"
    assert s["top_categories"][0]["count"] == 3


def test_review_logger_recent_empty(tmp_path):
    logger = ReviewLogger(log_dir=tmp_path / "none")
    assert logger.recent() == []
    assert logger.summarize()["reviews"] == 0


def test_review_logger_skips_corrupt_lines(tmp_path):
    logger = ReviewLogger(log_dir=tmp_path)
    logger.log("s", "hive", "static", [])
    with open(logger.log_file, "a", encoding="utf-8") as f:
        f.write("{broken json\n")
    logger.log("s2", "hive", "static", [])
    assert len(logger.recent()) == 2


# ---------------------------------------------------------------------------
# Fixer (mock LLM)
# ---------------------------------------------------------------------------

from seatunnel_agent.sql_review import fixer as fixer_mod


class _FakeResp:
    def __init__(self, text):
        self.reply_text = text


class _FakeLLM:
    def __init__(self, text):
        self._text = text

    def chat(self, system, messages, **kw):
        return _FakeResp(self._text)


def test_generate_fix_extracts_sql_block(monkeypatch):
    monkeypatch.setattr(
        fixer_mod, "LLMClient",
        lambda settings: _FakeLLM("before\n```sql\nselect id from t\n```\nafter"))
    out = fixer_mod.generate_fix(None, "select * from t", "hive", "report")
    assert out == "select id from t"


def test_generate_fix_accepts_bare_sql(monkeypatch):
    monkeypatch.setattr(
        fixer_mod, "LLMClient",
        lambda settings: _FakeLLM("SELECT id FROM t WHERE pt='1'"))
    out = fixer_mod.generate_fix(None, "select * from t", "hive", "report")
    assert out.startswith("SELECT id")


def test_generate_fix_no_sql_raises(monkeypatch):
    monkeypatch.setattr(
        fixer_mod, "LLMClient",
        lambda settings: _FakeLLM("I cannot help with that."))
    with pytest.raises(RuntimeError, match="修复"):
        fixer_mod.generate_fix(None, "select * from t", "hive", "report")


# ---------------------------------------------------------------------------
# CLI: --dir / --fail-on / --rules / --output
# ---------------------------------------------------------------------------

from click.testing import CliRunner

from seatunnel_agent.cli import cli as _cli_root


def _run_cli(args):
    return CliRunner().invoke(_cli_root, args)


def test_cli_review_static_inline():
    r = _run_cli(["review", "--sql", "select id from t where pt='1'",
                  "--static-only"])
    assert r.exit_code == 0
    assert "CR 报告" in r.output


def test_cli_review_fail_on_gate():
    r = _run_cli(["review", "--sql", "select * from t order by id",
                  "--static-only", "--fail-on", "risk"])
    assert r.exit_code == 1
    r2 = _run_cli(["review", "--sql", "select * from t order by id",
                   "--static-only", "--fail-on", "critical"])
    assert r2.exit_code == 0


def test_cli_review_dir_batch(tmp_path):
    (tmp_path / "a.sql").write_text("select * from t where pt='1'",
                                    encoding="utf-8")
    (tmp_path / "b.sql").write_text("select id from t where pt='1'",
                                    encoding="utf-8")
    r = _run_cli(["review", "--dir", str(tmp_path), "--static-only"])
    assert r.exit_code == 0
    assert "a.sql" in r.output and "b.sql" in r.output
    assert "批量审查汇总" in r.output


def test_cli_review_dir_empty_errors(tmp_path):
    r = _run_cli(["review", "--dir", str(tmp_path), "--static-only"])
    assert r.exit_code != 0


def test_cli_review_no_input_errors():
    r = _run_cli(["review", "--static-only"])
    assert r.exit_code != 0


def test_cli_review_output_file(tmp_path):
    out = tmp_path / "report.md"
    r = _run_cli(["review", "--sql", "select id from t where pt='1'",
                  "--static-only", "-o", str(out)])
    assert r.exit_code == 0
    assert "CR 报告" in out.read_text(encoding="utf-8")


def test_cli_review_rules_file(tmp_path):
    rules = tmp_path / ".sqlreview.yaml"
    rules.write_text("disable: [resource_usage]\nfail_on: risk\n",
                     encoding="utf-8")
    r = _run_cli(["review", "--sql", "select * from t where pt='1'",
                  "--static-only", "--rules", str(rules)])
    assert r.exit_code == 0
    assert "SELECT *" not in r.output


def test_cli_review_rules_fail_on_from_config(tmp_path):
    rules = tmp_path / ".sqlreview.yaml"
    rules.write_text("fail_on: risk\n", encoding="utf-8")
    r = _run_cli(["review", "--sql", "select * from t order by id",
                  "--static-only", "--rules", str(rules)])
    assert r.exit_code == 1


def test_cli_review_bad_rules_file(tmp_path):
    rules = tmp_path / "rules.yaml"
    rules.write_text("bogus: 1\n", encoding="utf-8")
    r = _run_cli(["review", "--sql", "select 1", "--static-only",
                  "--rules", str(rules)])
    assert r.exit_code != 0


def test_cli_review_stats_runs():
    r = _run_cli(["review-stats"])
    assert r.exit_code == 0


def test_cli_review_dedupes_overlapping_sources(tmp_path):
    f = tmp_path / "a.sql"
    f.write_text("select id from t where pt='1'", encoding="utf-8")
    # --file and --dir both resolve to the same file -> reviewed once
    r = _run_cli(["review", "--file", str(f), "--dir", str(tmp_path),
                  "--static-only"])
    assert r.exit_code == 0
    assert "批量审查汇总" not in r.output


# ---------------------------------------------------------------------------
# Multi-statement splitting
# ---------------------------------------------------------------------------

def test_split_statements_top_level_semicolon():
    from seatunnel_agent.sql_review.linter import split_statements
    sql = "SELECT 1;\nSELECT 2"
    parts = split_statements(sql)
    assert len(parts) == 2
    assert parts[0][0] == 0
    # the second segment keeps its leading newline, so offset + local line = 2
    off, seg = parts[1]
    assert off + seg[:seg.index("SELECT")].count("\n") + 1 == 2


def test_split_statements_ignores_semicolon_in_parens_and_strings():
    from seatunnel_agent.sql_review.linter import split_statements
    sql = "SELECT concat(a, ';') FROM (SELECT 1) t"
    assert len(split_statements(sql)) == 1


def test_split_statements_empty_returns_whole():
    from seatunnel_agent.sql_review.linter import split_statements
    assert split_statements("") == [(0, "")]


def test_lint_multi_statement_line_numbers_remapped():
    sql = "SELECT id FROM t WHERE pt='1';\nSELECT * FROM b"
    fs = by_category(lint_sql(sql), "resource_usage")
    star = [f for f in fs if "SELECT *" in f.description]
    assert star and "行 2" in star[0].location


def test_lint_multi_statement_each_checked():
    sql = "SELECT * FROM a;\nSELECT * FROM b"
    fs = [f for f in lint_sql(sql) if "SELECT *" in f.description]
    assert len(fs) == 2
    assert {"行 1", "行 2"} <= {f.location for f in fs}


# ---------------------------------------------------------------------------
# Inline disable comments
# ---------------------------------------------------------------------------

def test_inline_disable_same_line():
    fs = lint_sql("SELECT * FROM a -- sqlreview-disable")
    assert fs == []


def test_inline_disable_next_line_with_category():
    sql = "-- sqlreview-disable-next-line: resource_usage\nSELECT * FROM a"
    assert lint_sql(sql) == []


def test_inline_disable_wrong_category_kept():
    sql = "-- sqlreview-disable-next-line: readability\nSELECT * FROM a"
    assert "resource_usage" in categories(lint_sql(sql))


def test_inline_disable_file_scope():
    sql = "-- sqlreview-disable-file\nSELECT * FROM a;\nSELECT * FROM b"
    assert lint_sql(sql) == []


def test_inline_disable_file_scope_with_category():
    sql = ("-- sqlreview-disable-file: resource_usage\n"
           "SELECT a.x FROM a JOIN b")
    fs = lint_sql(sql)
    assert "resource_usage" not in categories(fs)
    assert "join_cartesian" in categories(fs)  # JOIN without ON still flagged


# ---------------------------------------------------------------------------
# Complexity scoring
# ---------------------------------------------------------------------------

def test_complexity_deep_subquery_nesting():
    sql = ("SELECT * FROM (SELECT * FROM (SELECT * FROM "
           "(SELECT id FROM t) x) y) z")
    fs = by_category(lint_sql(sql), "readability")
    assert any("子查询嵌套" in f.description for f in fs)


def test_complexity_shallow_nesting_ok():
    sql = "SELECT id FROM (SELECT id FROM t WHERE pt='1') x"
    fs = by_category(lint_sql(sql), "readability")
    assert not any("子查询嵌套" in f.description for f in fs)


def test_complexity_many_joins():
    joins = " ".join(f"JOIN t{i} ON t0.id = t{i}.id" for i in range(1, 7))
    sql = f"SELECT t0.id FROM t0 {joins} WHERE t0.pt='1'"
    fs = by_category(lint_sql(sql), "readability")
    assert any("JOIN（阈值" in f.description for f in fs)


def test_complexity_long_statement():
    sql = "SELECT id\nFROM t\nWHERE pt='1'" + "\n" * 210
    fs = by_category(lint_sql(sql), "readability")
    assert any("行（阈值" in f.description for f in fs)


# ---------------------------------------------------------------------------
# Custom regex rules
# ---------------------------------------------------------------------------

def test_custom_rule_fires():
    from seatunnel_agent.sql_review.config import _parse_config
    cfg = _parse_config({"custom_rules": [
        {"pattern": r"\border\s+by\b", "message": "禁止 ORDER BY",
         "severity": "critical", "category": "resource_usage",
         "suggestion": "用 SORT BY"},
    ]})
    fs = lint_sql("SELECT id FROM t WHERE pt='1' ORDER BY id LIMIT 10",
                  config=cfg)
    hit = [f for f in fs if f.description == "禁止 ORDER BY"]
    assert hit and hit[0].severity is Severity.CRITICAL
    assert hit[0].suggestion == "用 SORT BY"


def test_custom_rule_validation_errors():
    from seatunnel_agent.sql_review.config import _parse_config
    with pytest.raises(ValueError, match="必须是规则列表"):
        _parse_config({"custom_rules": {"pattern": "x"}})
    with pytest.raises(ValueError, match="缺少 pattern"):
        _parse_config({"custom_rules": [{"message": "m"}]})
    with pytest.raises(ValueError, match="缺少 message"):
        _parse_config({"custom_rules": [{"pattern": "x"}]})
    with pytest.raises(ValueError, match="pattern 无效"):
        _parse_config({"custom_rules": [{"pattern": "([", "message": "m"}]})
    with pytest.raises(ValueError, match="severity 无效"):
        _parse_config({"custom_rules": [
            {"pattern": "x", "message": "m", "severity": "fatal"}]})
    with pytest.raises(ValueError, match="未知检查类别"):
        _parse_config({"custom_rules": [
            {"pattern": "x", "message": "m", "category": "nope"}]})
    with pytest.raises(ValueError, match="未知字段"):
        _parse_config({"custom_rules": [
            {"pattern": "x", "message": "m", "extra": 1}]})


def test_custom_rule_defaults():
    from seatunnel_agent.sql_review.config import _parse_config
    cfg = _parse_config({"custom_rules": [{"pattern": "x", "message": "m"}]})
    rule = cfg.custom_rules[0]
    assert rule.severity is Severity.SUGGESTION
    assert rule.category == "readability"


def test_custom_rule_survives_disabled_category():
    # `disable: [readability]` must not swallow the user's own custom rule
    from seatunnel_agent.sql_review.config import _parse_config
    cfg = _parse_config({
        "disable": ["readability"],
        "custom_rules": [{"pattern": r"\bfoo\b", "message": "no foo"}],
    })
    fs = lint_sql("SELECT foo FROM t WHERE pt='1'", config=cfg)
    assert any(f.description == "no foo" for f in fs)


def test_custom_rule_severity_not_clobbered_by_override():
    from seatunnel_agent.sql_review.config import _parse_config
    cfg = _parse_config({
        "severity": {"readability": "suggestion"},
        "custom_rules": [{"pattern": r"\bfoo\b", "message": "no foo",
                          "severity": "critical"}],
    })
    fs = [f for f in lint_sql("SELECT foo FROM t WHERE pt='1'", config=cfg)
          if f.description == "no foo"]
    assert fs and fs[0].severity is Severity.CRITICAL


def test_custom_rule_match_cap():
    from seatunnel_agent.sql_review.config import _parse_config
    from seatunnel_agent.sql_review.linter import _MAX_CUSTOM_MATCHES
    cfg = _parse_config({"custom_rules": [
        {"pattern": r"\bfoo\b", "message": "no foo"}]})
    sql = "SELECT " + ", ".join(["foo"] * 100) + " FROM t WHERE pt='1'"
    fs = [f for f in lint_sql(sql, config=cfg) if f.description == "no foo"]
    assert len(fs) == _MAX_CUSTOM_MATCHES


def test_custom_rule_category_case_insensitive():
    from seatunnel_agent.sql_review.config import _parse_config
    cfg = _parse_config({"custom_rules": [
        {"pattern": "x", "message": "m", "category": "Readability"}]})
    assert cfg.custom_rules[0].category == "readability"


def test_custom_rule_finding_source_is_custom():
    from seatunnel_agent.sql_review.config import _parse_config
    cfg = _parse_config({"custom_rules": [
        {"pattern": r"\bfoo\b", "message": "no foo"}]})
    fs = [f for f in lint_sql("SELECT foo FROM t WHERE pt='1'", config=cfg)
          if f.description == "no foo"]
    assert fs[0].source == "custom"


def test_inline_disable_in_string_literal_ignored():
    # directive text inside a string literal must not suppress anything
    sql = "SELECT * FROM a WHERE note = '-- sqlreview-disable'"
    assert "resource_usage" in categories(lint_sql(sql))


def test_inline_disable_in_block_comment_ignored():
    sql = "/* -- sqlreview-disable */\nSELECT * FROM a"
    assert "resource_usage" in categories(lint_sql(sql))


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------

def test_baseline_roundtrip(tmp_path):
    from seatunnel_agent.sql_review.baseline import (
        load_baseline, save_baseline, split_by_baseline,
    )
    f1 = _mk_finding(Severity.RISK)
    path = tmp_path / "base.json"
    n = save_baseline(path, [("a.sql", f1)])
    assert n == 1
    prints = load_baseline(path)
    new, known = split_by_baseline("a.sql", [f1], prints)
    assert new == [] and known == [f1]
    # different file label -> not suppressed
    new2, known2 = split_by_baseline("b.sql", [f1], prints)
    assert new2 == [f1] and known2 == []


def test_baseline_fingerprint_path_normalized(tmp_path):
    from seatunnel_agent.sql_review.baseline import save_baseline, split_by_baseline, load_baseline
    f1 = _mk_finding(Severity.RISK)
    path = tmp_path / "base.json"
    save_baseline(path, [("sql\\a.sql", f1)])
    prints = load_baseline(path)
    new, known = split_by_baseline("sql/a.sql", [f1], prints)
    assert known == [f1]


def test_baseline_invalid_file(tmp_path):
    from seatunnel_agent.sql_review.baseline import load_baseline
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="解析失败"):
        load_baseline(bad)
    bad.write_text('{"no": "findings"}', encoding="utf-8")
    with pytest.raises(ValueError, match="格式无效"):
        load_baseline(bad)
    with pytest.raises(ValueError, match="不存在"):
        load_baseline(tmp_path / "missing.json")


def test_cli_baseline_workflow(tmp_path):
    f = tmp_path / "q.sql"
    f.write_text("SELECT * FROM a", encoding="utf-8")
    base = tmp_path / "base.json"
    r1 = _run_cli(["review", str(f), "--static-only",
                   "--update-baseline", "--baseline", str(base)])
    assert r1.exit_code == 0 and base.is_file()
    # gate passes because the known finding is suppressed
    r2 = _run_cli(["review", str(f), "--static-only",
                   "--baseline", str(base), "--fail-on", "risk"])
    assert r2.exit_code == 0
    assert "基线抑制" in r2.output
    # without the baseline the same gate fails
    r3 = _run_cli(["review", str(f), "--static-only", "--fail-on", "risk"])
    assert r3.exit_code == 1


# ---------------------------------------------------------------------------
# JSON / SARIF output
# ---------------------------------------------------------------------------

def test_formats_json_single_source():
    import json as _json
    from seatunnel_agent.sql_review.agent import static_review_report
    from seatunnel_agent.sql_review.formats import results_to_json
    rep = static_review_report("SELECT * FROM a", "hive")
    doc = _json.loads(results_to_json([("q.sql", rep)]))
    assert doc["source"] == "q.sql"
    assert doc["findings"] and doc["findings"][0]["line"] == 1
    assert "stats" in doc


def test_formats_json_multi_source_is_list():
    import json as _json
    from seatunnel_agent.sql_review.agent import static_review_report
    from seatunnel_agent.sql_review.formats import results_to_json
    rep = static_review_report("SELECT 1", "hive")
    doc = _json.loads(results_to_json([("a.sql", rep), ("b.sql", rep)]))
    assert isinstance(doc, list) and len(doc) == 2


def test_formats_sarif_structure():
    import json as _json
    from seatunnel_agent.sql_review.agent import static_review_report
    from seatunnel_agent.sql_review.formats import results_to_sarif
    rep = static_review_report("SELECT * FROM a", "hive")
    doc = _json.loads(results_to_sarif([("sql\\q.sql", rep)]))
    assert doc["version"] == "2.1.0"
    run = doc["runs"][0]
    assert run["tool"]["driver"]["name"] == "seatunnel-sqlreview"
    res = run["results"][0]
    assert res["level"] in ("error", "warning", "note")
    loc = res["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "sql/q.sql"  # backslash normalized
    assert loc["region"]["startLine"] >= 1


def test_cli_format_json(tmp_path):
    import json as _json
    r = _run_cli(["review", "--sql", "SELECT * FROM a",
                  "--static-only", "--format", "json"])
    assert r.exit_code == 0
    doc = _json.loads(r.output[r.output.index("{"):])
    assert doc["findings"]
    assert "CR report" not in r.output


def test_cli_format_sarif_to_file(tmp_path):
    import json as _json
    out = tmp_path / "results.sarif"
    r = _run_cli(["review", "--sql", "SELECT * FROM a", "--static-only",
                  "--format", "sarif", "-o", str(out)])
    assert r.exit_code == 0
    doc = _json.loads(out.read_text(encoding="utf-8"))
    assert doc["runs"][0]["results"]


# ---------------------------------------------------------------------------
# Column lineage
# ---------------------------------------------------------------------------

def test_column_lineage_extracted():
    from seatunnel_agent.sql_review.lineage import extract_table_lineage
    lin = extract_table_lineage(
        "INSERT OVERWRITE TABLE dw.t SELECT a.id, SUM(a.amt) AS total "
        "FROM ods.pay a GROUP BY a.id"
    )
    outputs = {c["output"]: c for c in lin.columns}
    assert outputs["id"]["source"] == "ods.pay.id"
    assert outputs["total"]["aggregated"] is True


def test_column_lineage_in_rendered_report():
    from seatunnel_agent.sql_review.agent import static_review_report
    md = render_report(static_review_report(
        "SELECT a.id FROM ods.pay a WHERE a.pt='1'", "hive"))
    assert "列级血缘" in md
    assert "id ← ods.pay.id" in md


def test_column_lineage_in_to_dict():
    from seatunnel_agent.sql_review.lineage import extract_table_lineage
    lin = extract_table_lineage("SELECT a.id FROM t a")
    assert "columns" in lin.to_dict()


# ---------------------------------------------------------------------------
# CLI positional paths (pre-commit style)
# ---------------------------------------------------------------------------

def test_cli_positional_paths(tmp_path):
    f1 = tmp_path / "a.sql"
    f2 = tmp_path / "b.sql"
    f1.write_text("select id from t where pt='1'", encoding="utf-8")
    f2.write_text("select id from u where pt='1'", encoding="utf-8")
    r = _run_cli(["review", str(f1), str(f2), "--static-only"])
    assert r.exit_code == 0
    assert "批量审查汇总" in r.output


def test_cli_positional_dir(tmp_path):
    (tmp_path / "a.sql").write_text("select 1", encoding="utf-8")
    r = _run_cli(["review", str(tmp_path), "--static-only"])
    assert r.exit_code == 0


# ---------------------------------------------------------------------------
# Quality-pass regressions
# ---------------------------------------------------------------------------

def test_partition_cols_with_regex_metachars_do_not_crash():
    # user config values are escaped before being embedded in patterns
    cfg = ReviewConfig(partition_cols=("dt(1)", "a|b"))
    sql = "select id from zz.dwd_order_di"
    fs = by_category(lint_sql(sql, "hive", config=cfg), "partition_pruning")
    assert fs  # no re.error, table still flagged as unfiltered


def test_changed_sql_files_from_subdirectory(tmp_path):
    import subprocess
    from seatunnel_agent.sql_review.runner import changed_sql_files

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True,
                       capture_output=True)

    git("init")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / "sql").mkdir()
    f = tmp_path / "sql" / "q.sql"
    f.write_text("select 1", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "init")
    f.write_text("select 2", encoding="utf-8")

    sub = tmp_path / "sub"
    sub.mkdir()
    # git diff prints repo-root-relative paths; resolving them must work
    # even when invoked from a subdirectory of the repo
    files = changed_sql_files("HEAD", cwd=sub)
    assert [p.name for p in files] == ["q.sql"]
    assert all(p.is_file() for p in files)


# ---------------------------------------------------------------------------
# lineage_context failure-retry cache
# ---------------------------------------------------------------------------

def test_lineage_context_failure_retries_after_timeout(tmp_path, monkeypatch):
    from seatunnel_agent.sql_review import lineage_context as lc

    lc.reset_lineage_cache()
    monkeypatch.setenv("LINEAGE_SQL_DIR", str(tmp_path))
    monkeypatch.delenv("LINEAGE_SEATUNNEL_DIR", raising=False)

    # empty dir -> empty graph -> failure hint cached
    graph, hint = lc.get_lineage_graph()
    assert graph is None
    assert hint

    # fix the directory: within retry window the failure stays cached
    (tmp_path / "q.sql").write_text(
        "INSERT OVERWRITE TABLE zz.dws_t SELECT * FROM zz.dwd_s;", encoding="utf-8",
    )
    graph2, hint2 = lc.get_lineage_graph()
    assert graph2 is None
    assert hint2 == hint

    # after the retry window the build is attempted again and succeeds
    real_time = lc.time.time
    monkeypatch.setattr(
        lc.time, "time",
        lambda: real_time() + lc._FAILURE_RETRY_SECONDS + 1,
    )
    graph3, hint3 = lc.get_lineage_graph()
    assert graph3 is not None
    assert hint3 == ""
    lc.reset_lineage_cache()
