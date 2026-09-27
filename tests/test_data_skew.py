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


def test_null_key_not_borrowed_from_next_join():
    # the outer join has no ON of its own — the next join's ON must not be
    # misattributed to it as a NULL-key finding (it is DS006's cartesian case)
    sql = "select * from a left join b join c on b.id = c.id"
    findings, _ = detect_skew(sql, "spark", "zh")
    assert "DS007" not in keys(findings)
    assert "DS006" in keys(findings)


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


# ---------------------------------------------------------------------------
# probe: target extraction
# ---------------------------------------------------------------------------

from seatunnel_agent.data_skew.probe import (  # noqa: E402
    ProbeResult,
    ProbeTarget,
    extract_probe_targets,
    probe_lines_for_prompt,
    render_probe_section,
    run_probes,
)


def tkeys(targets):
    return {(t.table, t.column) for t in targets}


def test_extract_targets_join_keys_via_alias():
    sql = "SELECT * FROM orders o JOIN users u ON o.user_id = u.id"
    targets = extract_probe_targets(sql)
    assert tkeys(targets) == {("orders", "user_id"), ("users", "id")}
    assert all(t.reason == "join_key" for t in targets)


def test_extract_targets_bare_table_name_as_alias():
    sql = "SELECT * FROM orders JOIN users ON orders.user_id = users.id"
    assert tkeys(extract_probe_targets(sql)) == {
        ("orders", "user_id"),
        ("users", "id"),
    }


def test_extract_targets_db_qualified_table():
    sql = "SELECT * FROM dw.orders o JOIN dw.users u ON o.uid = u.id"
    assert tkeys(extract_probe_targets(sql)) == {("dw.orders", "uid"), ("dw.users", "id")}


def test_extract_targets_subquery_alias_skipped():
    sql = (
        "SELECT * FROM orders o "
        "JOIN (SELECT id FROM users WHERE active = 1) v ON o.user_id = v.id"
    )
    targets = extract_probe_targets(sql)
    # v resolves to nothing probeable at the outer level; users.id comes only
    # from the inner FROM being in the alias map — o.user_id must be present.
    assert ("orders", "user_id") in tkeys(targets)
    assert not any(t.table.lower() == "v" for t in targets)


def test_extract_targets_count_distinct_single_table():
    sql = "SELECT COUNT(DISTINCT user_id) FROM orders"
    targets = extract_probe_targets(sql)
    assert tkeys(targets) == {("orders", "user_id")}
    assert targets[0].reason == "count_distinct"


def test_extract_targets_count_distinct_qualified():
    sql = "SELECT COUNT(DISTINCT o.user_id) FROM orders o JOIN users u ON o.uid = u.id"
    targets = extract_probe_targets(sql)
    assert ("orders", "user_id") in tkeys(targets)


def test_extract_targets_count_distinct_multi_table_unqualified_skipped():
    sql = "SELECT COUNT(DISTINCT user_id) FROM orders o JOIN users u ON o.uid = u.id"
    targets = extract_probe_targets(sql)
    assert ("orders", "user_id") not in tkeys(targets)
    assert ("users", "user_id") not in tkeys(targets)


def test_extract_targets_dedupe_and_cap():
    sql = "SELECT * FROM a JOIN b ON a.k = b.k JOIN c ON a.k = c.k JOIN d ON a.k = d.k"
    targets = extract_probe_targets(sql, max_targets=3)
    assert len(targets) == 3
    assert len(tkeys(targets)) == 3


def test_extract_targets_ignores_string_literals():
    sql = "SELECT * FROM t WHERE note = 'from x join y on x.a = y.b'"
    assert extract_probe_targets(sql) == []


def test_extract_targets_cte_not_probed():
    # a CTE is not a physical table: probing "orders" here would hit an
    # unrelated real table of the same name (or fail outright)
    sql = (
        "WITH orders AS (SELECT * FROM raw_orders WHERE dt = 'x') "
        "SELECT * FROM orders o JOIN users u ON o.uid = u.id"
    )
    got = tkeys(extract_probe_targets(sql))
    assert not any(t == "orders" for t, _ in got)
    assert ("users", "id") in got


def test_extract_targets_cte_with_column_list_not_probed():
    sql = (
        "WITH tmp (k, n) AS (SELECT k, count(*) FROM raw GROUP BY k) "
        "SELECT * FROM tmp t JOIN dim d ON t.k = d.k"
    )
    got = tkeys(extract_probe_targets(sql))
    assert not any(t == "tmp" for t, _ in got)
    assert ("dim", "k") in got


# ---------------------------------------------------------------------------
# probe: execution (real sqlite database)
# ---------------------------------------------------------------------------

def _sqlite_executor(tmp_path, setup_sql):
    import sqlite3

    from seatunnel_agent.text2sql.executor.base import DatabaseConfig, create_executor

    db = tmp_path / "probe.db"
    conn = sqlite3.connect(db)
    conn.executescript(setup_sql)
    conn.commit()
    conn.close()
    return create_executor(
        DatabaseConfig(ds_type="sqlite", host="", port=0, database=str(db))
    )


def test_run_probes_confirms_hot_key_and_nulls(tmp_path):
    rows = []
    rows += ["(1, 'hot')"] * 40          # 40% hot key
    rows += [f"({i}, 'k{i}')" for i in range(2, 47)]  # 45 distinct
    rows += ["(999, NULL)"] * 15         # 15% NULL
    setup = (
        "CREATE TABLE orders (id INTEGER, user_id TEXT);"
        + "INSERT INTO orders VALUES " + ",".join(rows) + ";"
    )
    ex = _sqlite_executor(tmp_path, setup)
    results = run_probes(ex, [ProbeTarget("orders", "user_id", "join_key")])
    r = results[0]
    assert r.error == ""
    assert r.total == 100
    assert r.null_count == 15
    assert abs(r.null_ratio - 0.15) < 1e-9
    assert r.top[0] == ("hot", 40)
    assert abs(r.top1_ratio - 0.40) < 1e-9
    assert r.verdict == "confirmed"


def test_run_probes_balanced_is_ok(tmp_path):
    rows = ",".join(f"({i}, 'u{i}')" for i in range(100))
    setup = f"CREATE TABLE t (id INTEGER, k TEXT); INSERT INTO t VALUES {rows};"
    ex = _sqlite_executor(tmp_path, setup)
    r = run_probes(ex, [ProbeTarget("t", "k", "count_distinct")])[0]
    assert r.verdict == "ok"
    assert r.total == 100
    assert r.null_count == 0
    assert len(r.top) == 10  # LIMIT TOP_N respected


def test_run_probes_null_share_alone_confirms(tmp_path):
    rows = ",".join(f"({i}, 'u{i}')" for i in range(88)) + "," + ",".join(
        f"({i}, NULL)" for i in range(88, 100)
    )
    setup = f"CREATE TABLE t (id INTEGER, k TEXT); INSERT INTO t VALUES {rows};"
    ex = _sqlite_executor(tmp_path, setup)
    r = run_probes(ex, [ProbeTarget("t", "k", "join_key")])[0]
    assert r.top[0] == ("NULL", 12)  # NULL rendered as literal string
    assert r.verdict == "confirmed"  # null_ratio 0.12 >= 0.10


def test_run_probes_empty_table(tmp_path):
    ex = _sqlite_executor(tmp_path, "CREATE TABLE t (k TEXT);")
    r = run_probes(ex, [ProbeTarget("t", "k", "join_key")])[0]
    assert r.total == 0
    assert r.verdict == "empty"


def test_run_probes_error_isolated_per_target(tmp_path):
    rows = ",".join(f"('u{i}')" for i in range(100))
    setup = f"CREATE TABLE good (k TEXT); INSERT INTO good VALUES {rows};"
    ex = _sqlite_executor(tmp_path, setup)
    results = run_probes(
        ex,
        [
            ProbeTarget("missing_table", "k", "join_key"),
            ProbeTarget("good", "k", "join_key"),
        ],
    )
    assert results[0].verdict == "error"
    assert results[0].error
    assert results[1].verdict == "ok"


def test_end_to_end_extract_then_probe(tmp_path):
    setup = (
        "CREATE TABLE orders (user_id TEXT);"
        "CREATE TABLE users (id TEXT);"
        "INSERT INTO orders VALUES " + ",".join(["('hot')"] * 30 + [f"('u{i}')" for i in range(70)]) + ";"
        "INSERT INTO users VALUES " + ",".join(f"('u{i}')" for i in range(50)) + ";"
    )
    ex = _sqlite_executor(tmp_path, setup)
    targets = extract_probe_targets(
        "SELECT * FROM orders o JOIN users u ON o.user_id = u.id"
    )
    results = run_probes(ex, targets)
    by_key = {(r.target.table, r.target.column): r for r in results}
    assert by_key[("orders", "user_id")].verdict == "confirmed"
    assert by_key[("users", "id")].verdict == "ok"


# ---------------------------------------------------------------------------
# probe: rendering
# ---------------------------------------------------------------------------

def _fake_result(verdict="confirmed"):
    r = ProbeResult(target=ProbeTarget("orders", "user_id", "join_key"))
    if verdict == "confirmed":
        r.total, r.null_count, r.top = 100, 0, [("hot", 40), ("b", 5)]
    elif verdict == "ok":
        r.total, r.null_count, r.top = 100, 0, [("a", 2), ("b", 2)]
    elif verdict == "error":
        r.error = "no such table: orders"
    return r


def test_render_probe_section_zh_and_en():
    zh = render_probe_section([_fake_result()], "zh")
    assert "## 倾斜验证（实测）" in zh
    assert "实测数据确认 1 个键存在倾斜" in zh
    assert "`orders.user_id`" in zh
    assert "40.0%" in zh
    en = render_probe_section([_fake_result()], "en")
    assert "## Skew Verification (measured)" in en
    assert "confirms skew on 1 key(s)" in en
    assert "⛔ skew confirmed" in en


def test_render_probe_section_no_targets():
    zh = render_probe_section([], "zh")
    assert "## 倾斜验证（实测）" in zh
    assert "未解析到可探查的基表键" in zh


def test_render_probe_section_clean_and_error_rows():
    md = render_probe_section([_fake_result("ok"), _fake_result("error")], "en")
    assert "No significant skew measured" in md
    assert "✅ balanced" in md
    assert "probe failed" in md
    assert "no such table" in md


def test_render_probe_section_escapes_multiline_values():
    r = ProbeResult(target=ProbeTarget("t", "k", "join_key"))
    r.total, r.top = 100, [("bad\nvalue|x", 40)]
    md = render_probe_section([r], "en")
    row = next(l for l in md.splitlines() if "`t.k`" in l)
    assert "\n" not in row  # value newline must not split the table row
    assert "bad value\\|x" in row


def test_probe_lines_for_prompt_escapes_multiline_values():
    r = ProbeResult(target=ProbeTarget("t", "k", "join_key"))
    r.total, r.top = 100, [("a\nb", 40)]
    lines = probe_lines_for_prompt([r], "en")
    assert "a\nb" not in lines  # raw value newline collapsed everywhere
    assert "a b=40" in lines
    assert "'a b' (40.0%)" in lines  # hot-values list uses the same escaping


def test_remove_section_line_anchored():
    from seatunnel_agent.data_skew_ui import _PROBE_HEAD_RE, _remove_section

    section = render_probe_section([_fake_result()], "en")
    report = "# Report\n\nbody text\n\n" + section
    assert _remove_section(report, _PROBE_HEAD_RE) == "# Report\n\nbody text"
    # A mid-sentence quote of the heading must NOT truncate the report.
    quoted = "# Report\n\nsee the ## Skew Verification (measured) section below\n"
    assert _remove_section(quoted, _PROBE_HEAD_RE) == quoted


def test_remove_section_only_touches_its_own_section():
    from seatunnel_agent.data_skew import consistency
    from seatunnel_agent.data_skew_ui import _CST_HEAD_RE, _PROBE_HEAD_RE, _remove_section

    probe_sec = render_probe_section([_fake_result()], "en")
    res = consistency.ConsistencyResult(comparable=True, orig_count=5, opt_count=5,
                                        rows_compared=True, rows_match=True)
    cst_sec = consistency.render_consistency_section(res, "en")
    report = "# Report\n\nbody\n\n" + probe_sec + "\n\n" + cst_sec
    without_probe = _remove_section(report, _PROBE_HEAD_RE)
    assert "Skew Verification" not in without_probe
    assert "Consistency Measurement" in without_probe
    without_cst = _remove_section(report, _CST_HEAD_RE)
    assert "Skew Verification" in without_cst
    assert "Consistency Measurement" not in without_cst


def test_probe_lines_for_prompt():
    lines = probe_lines_for_prompt([_fake_result(), _fake_result("error")], "en")
    # error result skipped → one target: measurement line + hot-values line
    assert lines.count("\n") == 1
    assert "orders.user_id" in lines
    assert "rows=100" in lines
    assert "top1=40.0%" in lines
    assert "hot=40" in lines
    assert "hot values: 'hot' (40.0%)" in lines


def test_agent_probe_context_injected_into_prompt(tmp_path):
    from seatunnel_agent.config import Settings
    from seatunnel_agent.data_skew.agent import DataSkewAgent

    captured = {}

    class FakeResp:
        reply_text = "## 优化后 SQL\n```sql\nselect 1\n```"

    class FakeLLM:
        def chat(self, system_prompt, messages, on_text_delta=None):
            captured["system"] = system_prompt
            return FakeResp()

    agent = DataSkewAgent(Settings(api_key="x"), dialect="spark", lang="zh")
    agent._llm = FakeLLM()
    agent.analyze(
        "select count(distinct a) from t",
        use_llm=True,
        output_path=tmp_path / "opt.sql",
        probe_context="- t.a (join key): rows=100, top1=40.0%",
    )
    assert "实测键值分布" in captured["system"]
    assert "top1=40.0%" in captured["system"]


# ---------------------------------------------------------------------------
# probe: sampling (TABLESAMPLE)
# ---------------------------------------------------------------------------

from seatunnel_agent.data_skew.probe import (  # noqa: E402
    _table_expr,
    effective_sample_pct,
    engine_params_for_results,
)


def test_effective_sample_pct_gating():
    assert effective_sample_pct("hive", 10) == 10
    assert effective_sample_pct("sparksql", 1) == 1
    assert effective_sample_pct("postgresql", 10) == 10
    # non-sampling engines and out-of-range values fall back to full scan
    assert effective_sample_pct("sqlite", 10) == 0
    assert effective_sample_pct("mysql", 10) == 0
    assert effective_sample_pct("hive", 0) == 0
    assert effective_sample_pct("hive", 100) == 0
    assert effective_sample_pct("", 10) == 0


def test_table_expr_dialect_syntax():
    assert _table_expr("orders", "hive", 10) == "orders TABLESAMPLE (10 PERCENT)"
    assert _table_expr("orders", "sparksql", 1) == "orders TABLESAMPLE (1 PERCENT)"
    assert _table_expr("orders", "postgresql", 10) == "orders TABLESAMPLE SYSTEM (10)"
    assert _table_expr("orders", "sqlite", 10) == "orders"
    assert _table_expr("orders", "hive", 0) == "orders"


def test_run_probes_sampling_ignored_on_sqlite(tmp_path):
    rows = ",".join(f"('u{i}')" for i in range(100))
    setup = f"CREATE TABLE t (k TEXT); INSERT INTO t VALUES {rows};"
    ex = _sqlite_executor(tmp_path, setup)
    r = run_probes(ex, [ProbeTarget("t", "k", "join_key")],
                   ds_type="sqlite", sample_pct=10)[0]
    assert r.error == ""       # TABLESAMPLE never reached sqlite
    assert r.total == 100


def test_render_probe_section_sampled_note():
    md = render_probe_section([_fake_result()], "en", sample_pct=10)
    assert "10% table sample" in md
    zh = render_probe_section([_fake_result()], "zh", sample_pct=1)
    assert "按 1% 表采样估算" in zh
    plain = render_probe_section([_fake_result()], "en")
    assert "table sample" not in plain


# ---------------------------------------------------------------------------
# probe: measured engine parameters
# ---------------------------------------------------------------------------

def test_engine_params_join_key_spark():
    block = engine_params_for_results([_fake_result()], "spark", "en")
    assert "spark.sql.adaptive.skewJoin.enabled=true" in block
    assert "skewedPartitionFactor=5" in block
    assert "spark.sql.shuffle.partitions" not in block  # no agg skew confirmed
    assert block.startswith("**Suggested engine settings")
    assert "```sql" in block


def test_engine_params_agg_hive_and_maxcompute():
    r = ProbeResult(target=ProbeTarget("t", "k", "count_distinct"))
    r.total, r.top = 100, [("hot", 40)]
    hive = engine_params_for_results([r], "hive", "zh")
    assert "hive.groupby.skewindata=true" in hive
    assert "hive.optimize.skewjoin" not in hive
    mc = engine_params_for_results([r], "maxcompute", "zh")
    assert "odps.sql.groupby.skewindata=true" in mc


def test_engine_params_empty_when_nothing_confirmed_or_unknown_dialect():
    assert engine_params_for_results([_fake_result("ok")], "spark", "en") == ""
    assert engine_params_for_results([_fake_result()], "presto", "en") == ""
    assert engine_params_for_results([], "spark", "en") == ""


def test_render_probe_section_appends_engine_params():
    md = render_probe_section([_fake_result()], "en", dialect="spark")
    assert "spark.sql.adaptive.skewJoin.enabled=true" in md
    md_zh = render_probe_section([_fake_result()], "zh", dialect="spark")
    assert "建议引擎参数" in md_zh
    plain = render_probe_section([_fake_result()], "en")
    assert "skewJoin" not in plain


# ---------------------------------------------------------------------------
# probe: hot values in the LLM prompt
# ---------------------------------------------------------------------------

def test_probe_lines_for_prompt_lists_hot_values():
    r = ProbeResult(target=ProbeTarget("orders", "user_id", "join_key"))
    r.total, r.null_count = 100, 12
    r.top = [("hot", 35), ("NULL", 12), ("warm", 6), ("cold", 1)]
    lines = probe_lines_for_prompt([r], "en")
    assert "hot values: 'hot' (35.0%), NULL (12.0%), 'warm' (6.0%)" in lines
    assert "'cold'" not in lines  # below the 5% suspect threshold
    zh = probe_lines_for_prompt([r], "zh")
    assert "热点值: 'hot' (35.0%)" in zh


def test_probe_lines_hot_values_null_appended_when_not_in_top():
    r = ProbeResult(target=ProbeTarget("t", "k", "join_key"))
    r.total, r.null_count = 100, 11
    r.top = [("hot", 30), ("a", 2)]  # NULL not among the listed top values
    lines = probe_lines_for_prompt([r], "en")
    assert "NULL (11.0%)" in lines


def test_probe_lines_balanced_target_has_no_hot_values():
    r = ProbeResult(target=ProbeTarget("t", "k", "join_key"))
    r.total, r.top = 100, [("a", 2), ("b", 2)]
    lines = probe_lines_for_prompt([r], "en")
    assert "hot values" not in lines
    assert "\n" not in lines


# ---------------------------------------------------------------------------
# consistency: extraction and comparison
# ---------------------------------------------------------------------------

from seatunnel_agent.data_skew.consistency import (  # noqa: E402
    ConsistencyResult,
    check_consistency,
    extract_single_select,
    render_consistency_section,
)


def test_extract_single_select_basic():
    assert extract_single_select("SELECT * FROM t") == "SELECT * FROM t"
    assert extract_single_select("  with x as (select 1) select * from x; ") \
        == "with x as (select 1) select * from x"


def test_extract_single_select_skips_leading_set_lines():
    sql = ("SET spark.sql.adaptive.enabled=true;\n"
           "SET hive.skewjoin.key=100000;\nSELECT * FROM t;")
    assert extract_single_select(sql) == "SELECT * FROM t"


def test_extract_single_select_refuses_writes_and_multi_statement():
    assert extract_single_select("INSERT INTO t SELECT * FROM s") is None
    assert extract_single_select("DROP TABLE t") is None
    assert extract_single_select("SELECT 1; SELECT 2") is None
    assert extract_single_select("") is None
    assert extract_single_select("SET a=1;") is None


def test_check_consistency_full_match(tmp_path):
    setup = ("CREATE TABLE t (id INTEGER, v TEXT);"
             "INSERT INTO t VALUES (1,'a'),(2,'b'),(3,'c');")
    ex = _sqlite_executor(tmp_path, setup)
    res = check_consistency(ex, "SELECT id, v FROM t ORDER BY id",
                            "SELECT id, v FROM t ORDER BY id DESC")
    assert res.comparable and res.error == ""
    assert res.orig_count == res.opt_count == 3
    assert res.rows_compared and res.rows_match  # order-insensitive


def test_check_consistency_count_mismatch(tmp_path):
    setup = ("CREATE TABLE t (id INTEGER);"
             "INSERT INTO t VALUES (1),(2),(3);")
    ex = _sqlite_executor(tmp_path, setup)
    res = check_consistency(ex, "SELECT id FROM t", "SELECT id FROM t WHERE id > 1")
    assert res.comparable
    assert (res.orig_count, res.opt_count) == (3, 2)
    assert not res.rows_compared


def test_check_consistency_same_count_different_rows(tmp_path):
    setup = ("CREATE TABLE t (id INTEGER);"
             "INSERT INTO t VALUES (1),(2),(3);")
    ex = _sqlite_executor(tmp_path, setup)
    res = check_consistency(ex, "SELECT id FROM t WHERE id <= 2",
                            "SELECT id FROM t WHERE id >= 2")
    assert res.orig_count == res.opt_count == 2
    assert res.rows_compared and not res.rows_match


def test_check_consistency_large_result_counts_only(tmp_path):
    rows = ",".join(f"({i})" for i in range(600))
    setup = f"CREATE TABLE t (id INTEGER); INSERT INTO t VALUES {rows};"
    ex = _sqlite_executor(tmp_path, setup)
    res = check_consistency(ex, "SELECT id FROM t", "SELECT id FROM t")
    assert res.orig_count == res.opt_count == 600
    assert not res.rows_compared  # above MAX_COMPARE_ROWS → count check only


def test_check_consistency_not_comparable_runs_nothing():
    calls = []

    class Spy:
        def run(self, sql, max_rows=0):
            calls.append(sql)

    res = check_consistency(Spy(), "INSERT INTO t SELECT 1", "SELECT 1")
    assert not res.comparable
    assert calls == []  # refused scripts never reach the database


def test_check_consistency_error_surfaced(tmp_path):
    ex = _sqlite_executor(tmp_path, "CREATE TABLE t (id INTEGER);")
    res = check_consistency(ex, "SELECT id FROM missing", "SELECT id FROM t")
    assert res.comparable
    assert res.error


def test_check_consistency_trailing_line_comment(tmp_path):
    # a trailing "-- comment" must not swallow the COUNT wrapper's ')'
    setup = "CREATE TABLE t (id INTEGER); INSERT INTO t VALUES (1),(2);"
    ex = _sqlite_executor(tmp_path, setup)
    res = check_consistency(ex, "SELECT id FROM t",
                            "SELECT id FROM t -- optimized by LLM")
    assert res.error == ""
    assert res.orig_count == res.opt_count == 2
    assert res.rows_compared and res.rows_match


def test_render_consistency_section_strings():
    ok = ConsistencyResult(comparable=True, orig_count=3, opt_count=3,
                           rows_compared=True, rows_match=True,
                           orig_ms=5, opt_ms=4)
    en = render_consistency_section(ok, "en")
    assert "## Consistency Measurement" in en
    assert "5 ms" in en
    zh = render_consistency_section(ok, "zh")
    assert "## 一致性实测" in zh

    bad = ConsistencyResult(comparable=True, orig_count=3, opt_count=2)
    assert render_consistency_section(bad, "en")

    differ = ConsistencyResult(comparable=True, orig_count=2, opt_count=2,
                               rows_compared=True, rows_match=False)
    assert render_consistency_section(differ, "en")

    nc = render_consistency_section(ConsistencyResult(), "en")
    assert "## Consistency Measurement" in nc

    err = render_consistency_section(
        ConsistencyResult(comparable=True, error="boom\nline2"), "zh")
    assert "boom line2" in err


# ---------------------------------------------------------------------------
# probe: GROUP BY keys
# ---------------------------------------------------------------------------

def _by_reason(sql):
    out = {}
    for t in extract_probe_targets(sql):
        out.setdefault(t.reason, []).append((t.table, t.column))
    return out


def test_extract_targets_group_by_single_table():
    got = _by_reason("SELECT dt, COUNT(*) FROM orders GROUP BY dt")
    assert got["group_key"] == [("orders", "dt")]


def test_extract_targets_group_by_qualified_multi_table():
    sql = ("SELECT o.dt, COUNT(*) FROM orders o JOIN users u "
           "ON o.uid = u.id GROUP BY o.dt")
    got = _by_reason(sql)
    assert ("orders", "dt") in got["group_key"]
    assert ("orders", "uid") in got["join_key"]  # join keys still extracted


def test_extract_targets_group_by_multiple_columns():
    got = _by_reason("SELECT dt, region FROM t GROUP BY dt, region")
    assert got["group_key"] == [("t", "dt"), ("t", "region")]


def test_extract_targets_group_by_skips_non_columns():
    # positional, expressions, ALL, rollup constructs — none probeable
    assert "group_key" not in _by_reason("SELECT 1 FROM t GROUP BY 1, 2")
    assert "group_key" not in _by_reason("SELECT date(c) FROM t GROUP BY date(c)")
    assert "group_key" not in _by_reason("SELECT a, b FROM t GROUP BY ALL")


def test_extract_targets_group_by_clause_ends_at_having():
    got = _by_reason("SELECT dt FROM t GROUP BY dt HAVING COUNT(*) > 10 ORDER BY dt")
    assert got["group_key"] == [("t", "dt")]


def test_extract_targets_group_by_bare_col_ambiguous_tables_skipped():
    sql = ("SELECT dt FROM a JOIN b ON a.id = b.id GROUP BY dt")
    got = _by_reason(sql)
    assert "group_key" not in got  # bare column, two candidate tables


def test_extract_targets_join_key_wins_dedup_over_group_key():
    sql = ("SELECT o.uid FROM orders o JOIN users u ON o.uid = u.id "
           "GROUP BY o.uid")
    targets = {(t.table, t.column): t.reason for t in extract_probe_targets(sql)}
    assert targets[("orders", "uid")] == "join_key"


def test_engine_params_agg_triggered_by_group_key():
    r = ProbeResult(target=ProbeTarget("t", "dt", "group_key"))
    r.total, r.top = 100, [("hot", 40)]
    block = engine_params_for_results([r], "spark", "en")
    assert "spark.sql.shuffle.partitions=400" in block
    assert "skewJoin" not in block


def test_render_probe_section_group_key_reason_label():
    r = ProbeResult(target=ProbeTarget("t", "dt", "group_key"))
    r.total, r.top = 100, [("hot", 40)]
    assert "GROUP BY key" in render_probe_section([r], "en")
    assert "GROUP BY 分组键" in render_probe_section([r], "zh")


# ---------------------------------------------------------------------------
# probe: parallel execution and cache
# ---------------------------------------------------------------------------

def test_run_probes_parallel_preserves_target_order(tmp_path):
    setup = "".join(
        f"CREATE TABLE t{i} (k TEXT); INSERT INTO t{i} VALUES " +
        ",".join(f"('v{j}')" for j in range(20)) + ";"
        for i in range(6)
    )
    ex = _sqlite_executor(tmp_path, setup)
    targets = [ProbeTarget(f"t{i}", "k", "join_key") for i in range(6)]
    results = run_probes(ex, targets)
    assert [r.target.table for r in results] == [f"t{i}" for i in range(6)]
    assert all(r.error == "" and r.total == 20 for r in results)


def test_probe_cache_roundtrip():
    from seatunnel_agent.data_skew.probe import ProbeCache

    c = ProbeCache()
    key = ("select 1", "sqlite", 0)
    assert c.get(key) is None
    results = [_fake_result()]
    c.put(key, results)
    assert c.get(key) is results
    # any component of the key changing is a miss
    assert c.get(("select 2", "sqlite", 0)) is None
    assert c.get(("select 1", "hive", 0)) is None
    assert c.get(("select 1", "sqlite", 10)) is None
    # a new run replaces the previous entry
    c.put(("select 2", "sqlite", 0), [])
    assert c.get(key) is None
    c.clear()
    assert c.get(("select 2", "sqlite", 0)) is None


# ---------------------------------------------------------------------------
# probe: GROUP BY clause termination and measured hot-value hints
# ---------------------------------------------------------------------------

def test_group_by_stops_at_distribute_by():
    sql = "INSERT OVERWRITE TABLE d SELECT dt, count(*) FROM ods.t GROUP BY dt DISTRIBUTE BY rand()"
    targets = extract_probe_targets(sql)
    cols = {(t.table, t.column) for t in targets}
    assert ("ods.t", "dt") in cols
    # DISTRIBUTE BY arguments never become probe targets
    assert all(t.column != "rand" for t in targets)


def test_engine_params_include_measured_hot_values():
    r = _fake_result()  # confirmed join_key with hot value "hot" at 40%
    block = engine_params_for_results([r], "spark", "zh")
    assert "实测热点值" in block and "'hot'" in block
    block_en = engine_params_for_results([r], "spark", "en")
    assert "measured hot values" in block_en


def test_engine_params_maxcompute_skewjoin_hint_with_values():
    r = _fake_result()
    block = engine_params_for_results([r], "maxcompute", "zh")
    assert "/*+ SKEWJOIN(orders(user_id)((hot)(b))) */" in block


def test_engine_params_no_hint_without_hot_values():
    r = _fake_result()
    r.top = []            # confirmed via NULL ratio only
    r.null_count = 30
    block = engine_params_for_results([r], "maxcompute", "zh")
    assert "SKEWJOIN(orders" not in block
    assert "odps.sql.skewjoin" in block.replace("SET ", "").lower() or "skewjoin=true" in block


# ---------------------------------------------------------------------------
# analysis history (logs/data_skew.jsonl)
# ---------------------------------------------------------------------------

def test_history_log_and_recent(tmp_path):
    from seatunnel_agent.data_skew.agent import static_skew_report
    from seatunnel_agent.data_skew.history import SkewHistory

    h = SkewHistory(log_dir=tmp_path)
    rep = static_skew_report("SELECT count(distinct uid) FROM t", "spark", "zh")
    h.log("SELECT count(distinct uid) FROM t", rep, mode="static", source="cli")
    h.log("SELECT 1", static_skew_report("SELECT 1", "spark", "zh"),
          mode="static", source="ui")
    recs = h.recent(10)
    assert len(recs) == 2
    assert recs[0]["sql"] == "SELECT 1"          # newest first
    assert recs[1]["counts"]["medium"] == 1      # DS001 is medium
    assert recs[1]["verdict"] == "medium"
    assert recs[0]["verdict"] == "clean"
    assert recs[1]["source"] == "cli"


def test_history_recent_missing_file(tmp_path):
    from seatunnel_agent.data_skew.history import SkewHistory

    assert SkewHistory(log_dir=tmp_path / "nope").recent() == []


def test_default_history_env_override(tmp_path, monkeypatch):
    from seatunnel_agent.data_skew.history import default_history

    target = tmp_path / "isolated" / "hist.jsonl"
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH", str(target))
    h = default_history()
    assert h.log_file == target


# ---------------------------------------------------------------------------
# MCP tool functions (no mcp package needed)
# ---------------------------------------------------------------------------

def test_mcp_skew_check(tmp_path, monkeypatch):
    from seatunnel_agent.data_skew.mcp_server import build_tool_functions

    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    fns = build_tool_functions()
    out = fns["skew_check"]("SELECT count(distinct uid) FROM t")
    assert "数据倾斜分析报告" in out and "COUNT(DISTINCT)" in out
    out_en = fns["skew_check"]("SELECT count(distinct uid) FROM t", lang="en")
    assert "Data Skew Analysis Report" in out_en
    assert "不能为空" in fns["skew_check"]("   ")
    # history got both analyses
    from seatunnel_agent.data_skew.history import default_history
    assert len(default_history().recent()) == 2


def test_mcp_skew_check_file(tmp_path, monkeypatch):
    from seatunnel_agent.data_skew.mcp_server import build_tool_functions

    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    fns = build_tool_functions()
    f = tmp_path / "q.sql"
    f.write_text("SELECT * FROM t ORDER BY a", encoding="utf-8")
    assert "全局 ORDER BY" in fns["skew_check_file"](str(f))
    assert "cannot read file" in fns["skew_check_file"](str(tmp_path / "missing.sql"))


# ---------------------------------------------------------------------------
# CLI: seatunnel-agent skew
# ---------------------------------------------------------------------------

def _skew_cli(tmp_path, monkeypatch, args):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    return CliRunner().invoke(cli, ["skew", *args])


def test_cli_skew_inline_static(tmp_path, monkeypatch):
    res = _skew_cli(tmp_path, monkeypatch,
                    ["-s", "SELECT count(distinct uid) FROM t"])
    assert res.exit_code == 0, res.output
    assert "COUNT(DISTINCT)" in res.output


def test_cli_skew_fail_on_gate(tmp_path, monkeypatch):
    res = _skew_cli(tmp_path, monkeypatch,
                    ["-s", "SELECT * FROM t ORDER BY a", "--fail-on", "high"])
    assert res.exit_code == 1
    assert "检查未通过" in res.output
    res_ok = _skew_cli(tmp_path, monkeypatch,
                       ["-s", "SELECT id FROM t WHERE dt='2024-06-01'",
                        "--fail-on", "high"])
    assert res_ok.exit_code == 0, res_ok.output


def test_cli_skew_directory_json(tmp_path, monkeypatch):
    import json

    d = tmp_path / "sqls"
    d.mkdir()
    (d / "a.sql").write_text("SELECT count(distinct uid) FROM t",
                             encoding="utf-8")
    (d / "b.sql").write_text("SELECT id FROM t WHERE dt='2024-06-01'",
                             encoding="utf-8")
    res = _skew_cli(tmp_path, monkeypatch, ["-D", str(d), "-F", "json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert len(payload) == 2
    by_file = {p["file"]: p for p in payload}
    a = by_file[str(d / "a.sql")]
    assert a["counts"]["medium"] == 1
    assert a["findings"][0]["severity"] == "medium"


def test_cli_skew_output_file_and_history(tmp_path, monkeypatch):
    out = tmp_path / "report.md"
    res = _skew_cli(tmp_path, monkeypatch,
                    ["-s", "SELECT 1", "-o", str(out)])
    assert res.exit_code == 0, res.output
    assert "数据倾斜分析报告" in out.read_text(encoding="utf-8")
    from seatunnel_agent.data_skew.history import default_history
    recs = default_history().recent()
    assert len(recs) == 1 and recs[0]["source"] == "cli"
