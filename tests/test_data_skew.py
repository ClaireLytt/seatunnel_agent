# -*- coding: utf-8 -*-
"""Tests for the Data Skew agent (static detector, report, LLM parsing)."""

from __future__ import annotations

import pytest

from seatunnel_agent.data_skew import (
    Severity,
    SkewFinding,
    SkewReport,
    detect_skew,
    normalize_dialect,
    render_report,
    split_statements,
    static_skew_check,
    static_skew_report,
)
from seatunnel_agent.data_skew.agent import (
    extract_optimized_sql,
    parse_optimization_table,
)
from seatunnel_agent.data_skew.detector import clean_sql


def keys(findings):
    return {f.key for f in findings}


# ---------------------------------------------------------------------------
# dialect / utilities
# ---------------------------------------------------------------------------

def test_normalize_dialect():
    assert normalize_dialect("Spark SQL") == "spark"
    assert normalize_dialect("spark3") == "spark"
    assert normalize_dialect("ODPS") == "maxcompute"
    assert normalize_dialect("mc") == "maxcompute"
    assert normalize_dialect("MaxCompute SQL") == "maxcompute"
    assert normalize_dialect("Hive SQL") == "hive"
    assert normalize_dialect("hive") == "hive"
    assert normalize_dialect("unknown") == "spark"
    assert normalize_dialect("") == "spark"


def test_clean_sql_blanks_literals_and_comments():
    sql = "select 'union' as x -- order by\nfrom t /* join */"
    cleaned = clean_sql(sql)
    assert "union" not in cleaned.lower()
    assert "order by" not in cleaned.lower()
    assert "/* join */" not in cleaned
    assert len(cleaned) == len(sql)


def test_clean_sql_keeps_hints():
    sql = "select /*+ BROADCAST(d) */ * from t join d on t.id = d.id"
    assert "/*+ BROADCAST(d) */" in clean_sql(sql)


def test_split_statements():
    sql = "select 1;\nselect 2;\n"
    stmts = split_statements(sql)
    assert len(stmts) == 2
    # semicolon inside a string literal must not split
    sql2 = "select ';' as a from t"
    assert len(split_statements(sql2)) == 1


# ---------------------------------------------------------------------------
# detector rules
# ---------------------------------------------------------------------------

def test_count_distinct_detected():
    findings, _ = detect_skew(
        "select count(distinct user_id) from t group by dt", "spark", "zh")
    assert "DS001" in keys(findings)


def test_multiple_count_distinct_high():
    findings, _ = detect_skew(
        "select count(distinct a), count(distinct b) from t", "spark", "zh")
    assert "DS002" in keys(findings)
    ds002 = next(f for f in findings if f.key == "DS002")
    assert ds002.severity == Severity.HIGH


def test_union_dedup_detected_but_union_all_ok():
    findings, _ = detect_skew("select a from t union select a from s", "spark", "zh")
    assert "DS004" in keys(findings)
    findings2, _ = detect_skew(
        "select a from t union all select a from s", "spark", "zh")
    assert "DS004" not in keys(findings2)


def test_global_orderby_without_limit():
    findings, _ = detect_skew("select * from t order by a", "spark", "zh")
    assert "DS005" in keys(findings)
    findings2, _ = detect_skew("select * from t order by a limit 100", "spark", "zh")
    assert "DS005" not in keys(findings2)


def test_orderby_inside_over_not_flagged():
    sql = "select row_number() over (partition by c order by a) rn from t"
    findings, _ = detect_skew(sql, "spark", "zh")
    assert "DS005" not in keys(findings)


def test_cartesian_join_detected():
    findings, _ = detect_skew(
        "select * from a join b where a.x > 1", "spark", "zh")
    assert "DS006" in keys(findings)
    findings2, _ = detect_skew(
        "select * from a join b on a.id = b.id", "spark", "zh")
    assert "DS006" not in keys(findings2)


def test_cross_join_detected():
    findings, _ = detect_skew("select * from a cross join b", "spark", "zh")
    assert "DS006" in keys(findings)


def test_null_key_outer_join():
    sql = "select * from a left join b on a.uid = b.uid"
    findings, _ = detect_skew(sql, "spark", "zh")
    assert "DS007" in keys(findings)
    # coalesce guard suppresses the finding — and must NOT be re-flagged
    # as DS008 (it is the very remedy DS007 recommends)
    sql2 = "select * from a left join b on coalesce(a.uid, '-') = b.uid"
    findings2, _ = detect_skew(sql2, "spark", "zh")
    assert "DS007" not in keys(findings2)
    assert "DS008" not in keys(findings2)


def test_function_on_join_key():
    sql = "select * from a join b on cast(a.id as string) = b.id"
    findings, _ = detect_skew(sql, "spark", "zh")
    assert "DS008" in keys(findings)


def test_rand_in_join_condition():
    sql = "select * from a join b on a.id = concat(b.id, rand())"
    findings, _ = detect_skew(sql, "spark", "zh")
    assert "DS012" in keys(findings)
    assert next(f for f in findings if f.key == "DS012").severity == Severity.HIGH


def test_window_without_partition():
    sql = "select row_number() over (order by id) rn from t"
    findings, _ = detect_skew(sql, "spark", "zh")
    assert "DS009" in keys(findings)
    sql2 = "select row_number() over (partition by dt order by id) rn from t"
    findings2, _ = detect_skew(sql2, "spark", "zh")
    assert "DS009" not in keys(findings2)


def test_dynamic_partition_without_distribute():
    sql = "insert overwrite table ads.t partition (dt) select id, dt from s"
    findings, _ = detect_skew(sql, "spark", "zh")
    assert "DS010" in keys(findings)
    sql2 = sql + " distribute by dt"
    findings2, _ = detect_skew(sql2, "spark", "zh")
    assert "DS010" not in keys(findings2)


def test_too_many_joins():
    joins = " ".join(
        f"join t{i} on t0.id = t{i}.id" for i in range(1, 8))
    findings, _ = detect_skew(f"select * from t0 {joins}", "spark", "zh")
    assert "DS011" in keys(findings)


def test_broadcast_hint_suppresses_ds013():
    sql = "select /*+ BROADCAST(d) */ * from t join d on t.id = d.id"
    findings, _ = detect_skew(sql, "spark", "zh")
    assert "DS013" not in keys(findings)
    sql2 = "select * from t join d on t.id = d.id"
    findings2, _ = detect_skew(sql2, "spark", "zh")
    assert "DS013" in keys(findings2)


def test_literals_do_not_trigger_rules():
    sql = "select 'union all order by' as note from t"
    findings, _ = detect_skew(sql, "spark", "zh")
    assert "DS004" not in keys(findings)
    assert "DS005" not in keys(findings)


def test_ddl_only_statement_skipped():
    findings, _ = detect_skew("drop table if exists t", "spark", "zh")
    assert findings == []


def test_line_numbers_across_statements():
    sql = "select 1;\n\nselect count(distinct x) from t"
    findings, _ = detect_skew(sql, "spark", "zh")
    ds001 = next(f for f in findings if f.key == "DS001")
    assert ds001.line == 3


# --- regression tests for review fixes -------------------------------------

def test_count_distinct_nested_parens():
    sql = "select count(distinct coalesce(a, b)) from t"
    findings, _ = detect_skew(sql, "spark", "zh")
    ds001 = next(f for f in findings if f.key == "DS001")
    assert ds001.args["col"] == "coalesce(a, b)"
    assert "coalesce(a, b))" in ds001.before


def test_subquery_join_counted_not_cartesian():
    # JOIN (subquery) must be recognized as a join and, with ON present,
    # must not be flagged as cartesian even though the subquery contains SELECT
    sql = ("select * from big t "
           "join (select id from dim where dt='x') d on t.id = d.id")
    findings, _ = detect_skew(sql, "spark", "zh")
    assert "DS006" not in keys(findings)
    assert "DS013" in keys(findings)  # the join itself was counted


def test_subquery_join_without_on_is_cartesian():
    sql = "select * from big t join (select id from dim) d where t.x = 1"
    findings, _ = detect_skew(sql, "spark", "zh")
    assert "DS006" in keys(findings)


def test_outer_join_subquery_null_key_uses_outer_on():
    # the ON inside the subquery must not be mistaken for the outer join's ON
    sql = ("select * from a left join "
           "(select x.id from x join y on x.id = y.id) b "
           "on coalesce(a.id, '-') = b.id")
    findings, _ = detect_skew(sql, "spark", "zh")
    assert "DS007" not in keys(findings)


def test_dynamic_partition_multi_column():
    sql = "insert overwrite table t partition (dt, hr) select id, dt, hr from s"
    findings, _ = detect_skew(sql, "spark", "zh")
    ds010 = next(f for f in findings if f.key == "DS010")
    assert ds010.args["col"] == "dt, hr"


def test_dynamic_partition_mixed_static_dynamic():
    sql = "insert overwrite table t partition (region='cn', dt) select id, dt from s"
    findings, _ = detect_skew(sql, "spark", "zh")
    ds010 = next(f for f in findings if f.key == "DS010")
    assert ds010.args["col"] == "dt"


def test_static_partition_not_flagged():
    sql = "insert overwrite table t partition (dt='2024-01-01') select id from s"
    findings, _ = detect_skew(sql, "spark", "zh")
    assert "DS010" not in keys(findings)


def test_semi_join_recognized():
    sql = "select * from a left semi join b on a.id = b.id"
    findings, _ = detect_skew(sql, "spark", "zh")
    assert "DS006" not in keys(findings)


# ---------------------------------------------------------------------------
# dialect-specific texts & engine hints
# ---------------------------------------------------------------------------

def test_dialect_specific_suggestions():
    sql = "select count(distinct a) from t join d on t.id = d.id"
    f_spark, hints_spark = detect_skew(sql, "spark", "zh")
    f_mc, hints_mc = detect_skew(sql, "maxcompute", "zh")
    spark_sugg = next(f for f in f_spark if f.key == "DS001").suggestion
    mc_sugg = next(f for f in f_mc if f.key == "DS001").suggestion
    assert "approx_count_distinct" in spark_sugg
    assert "approx_count_distinct" not in mc_sugg
    assert any("skewJoin" in h for h in hints_spark)
    assert any("SKEWJOIN" in h for h in hints_mc)


def test_engine_hints_absent_when_clean():
    _, hints = detect_skew("select a from t where dt='x'", "spark", "zh")
    assert hints == []


# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------

def test_findings_bilingual():
    sql = "select count(distinct a) from t"
    zh, _ = detect_skew(sql, "spark", "zh")
    en, _ = detect_skew(sql, "spark", "en")
    assert "汇聚" in zh[0].description
    assert "funnels" in en[0].description
    assert zh[0].key == en[0].key == "DS001"


def test_report_rendering_bilingual():
    sql = "select count(distinct a) from t order by a"
    zh = static_skew_check(sql, "spark", "zh")
    en = static_skew_check(sql, "spark", "en")
    assert "数据倾斜分析报告" in zh
    assert "优化点说明" in zh
    assert "原写法" in zh
    assert "Data Skew Analysis Report" in en
    assert "Optimization Points" in en
    assert "Expected Benefit" in en


def test_report_clean_verdict():
    report = static_skew_check("select a from t where dt='x'", "spark", "zh")
    assert "未发现明显倾斜写法" in report


# ---------------------------------------------------------------------------
# report object
# ---------------------------------------------------------------------------

def test_static_skew_report_object():
    rep = static_skew_report(
        "select count(distinct a) from t; select 1 from s order by x", "spark", "zh")
    assert rep.dialect == "spark"
    assert rep.statement_count == 2
    assert rep.high and rep.medium is not None
    assert all(f.source == "static" for f in rep.findings)


def test_markdown_escaping_in_report():
    f = SkewFinding(
        severity=Severity.LOW, category="llm", location="-",
        description="a|b\nc", impact="x", suggestion="y",
        before="a|b", after="c`d", benefit="z", source="llm",
    )
    md = render_report(SkewReport(findings=[f]), "zh")
    assert "a\\|b" in md


# ---------------------------------------------------------------------------
# LLM reply parsing
# ---------------------------------------------------------------------------

_LLM_REPLY_ZH = """\
分析完成。

## 优化后 SQL
```sql
SELECT /*+ BROADCAST(d) */ a FROM t JOIN d ON t.id = d.id
```

## 一致性检查
- 广播提示不改变结果集。

## 优化点说明

| # | 优化点 | 原写法 | 优化后 | 预期收益 |
|---|--------|--------|--------|---------|
| 1 | 小表广播 | `JOIN d` | `/*+ BROADCAST(d) */ JOIN d` | 消除 shuffle |
| 2 | 两阶段聚合 | `count(distinct a)` | `GROUP BY 后 COUNT` | 消除单点 |
"""


def test_extract_optimized_sql():
    sql = extract_optimized_sql(_LLM_REPLY_ZH)
    assert sql.startswith("SELECT /*+ BROADCAST(d) */")


def test_parse_optimization_table():
    points = parse_optimization_table(_LLM_REPLY_ZH)
    assert len(points) == 2
    assert points[0].description == "小表广播"
    assert points[0].before == "JOIN d"
    assert points[1].benefit == "消除单点"
    assert all(p.source == "llm" for p in points)


def test_parse_english_reply_sections():
    reply = _LLM_REPLY_ZH.replace("## 优化后 SQL", "## Optimized SQL") \
        .replace("## 一致性检查", "## Consistency Check") \
        .replace("## 优化点说明", "## Optimization Points")
    assert extract_optimized_sql(reply).startswith("SELECT")
    assert len(parse_optimization_table(reply)) == 2


def test_extract_sql_fallback_without_headings():
    reply = "here\n```sql\nselect 1\n```"
    assert extract_optimized_sql(reply) == "select 1"


def test_heading_quoted_midline_not_a_section():
    # the heading text quoted inside a sentence must not start a section
    reply = ('先说明：下文的 "## 优化后 SQL" 一节给出结果。\n\n'
             "## 优化后 SQL\n```sql\nselect 2\n```\n")
    assert extract_optimized_sql(reply) == "select 2"


# ---------------------------------------------------------------------------
# agent static path (no LLM, no API key needed)
# ---------------------------------------------------------------------------

def test_agent_static_path(tmp_path):
    from seatunnel_agent.config import Settings
    from seatunnel_agent.data_skew.agent import DataSkewAgent

    agent = DataSkewAgent(Settings(api_key="x"), dialect="spark", lang="zh")
    result = agent.analyze("select count(distinct a) from t", use_llm=False)
    assert not result.used_llm
    assert "COUNT(DISTINCT" in result.markdown
    assert result.optimized_sql == ""
    assert result.output_file == ""


def test_agent_empty_sql_raises():
    from seatunnel_agent.config import Settings
    from seatunnel_agent.data_skew.agent import DataSkewAgent

    agent = DataSkewAgent(Settings(api_key="x"))
    with pytest.raises(ValueError):
        agent.analyze("   ")


def test_write_optimized_adds_sql_suffix(tmp_path):
    from seatunnel_agent.data_skew.agent import DataSkewAgent

    out = DataSkewAgent._write_optimized("select 1", tmp_path / "opt.txt")
    assert out is not None
    assert out.suffix == ".sql"
    assert out.read_text(encoding="utf-8").strip() == "select 1"
