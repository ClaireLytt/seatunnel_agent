"""Tests for the Data Skew agent (static detector, report, LLM parsing)."""

from __future__ import annotations

import pytest

from seatunnel_agent.agents.data.data_skew import (
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
from seatunnel_agent.agents.data.data_skew.agent import (
    extract_optimized_sql,
    parse_optimization_table,
)
from seatunnel_agent.agents.data.data_skew.detector import clean_sql


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
    from seatunnel_agent.agents.data.data_skew.agent import DataSkewAgent
    from seatunnel_agent.common.config import Settings

    agent = DataSkewAgent(Settings(api_key="x"), dialect="spark", lang="zh")
    result = agent.analyze("select count(distinct a) from t", use_llm=False)
    assert not result.used_llm
    assert "COUNT(DISTINCT" in result.markdown
    assert result.optimized_sql == ""
    assert result.output_file == ""


def test_agent_empty_sql_raises():
    from seatunnel_agent.agents.data.data_skew.agent import DataSkewAgent
    from seatunnel_agent.common.config import Settings

    agent = DataSkewAgent(Settings(api_key="x"))
    with pytest.raises(ValueError):
        agent.analyze("   ")


def test_write_optimized_adds_sql_suffix(tmp_path):
    from seatunnel_agent.agents.data.data_skew.agent import DataSkewAgent

    out = DataSkewAgent._write_optimized("select 1", tmp_path / "opt.txt")
    assert out is not None
    assert out.suffix == ".sql"
    assert out.read_text(encoding="utf-8").strip() == "select 1"


# ---------------------------------------------------------------------------
# probe: target extraction
# ---------------------------------------------------------------------------

from seatunnel_agent.agents.data.data_skew.probe import (
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

    from seatunnel_agent.agents.data.text2sql.executor.base import (
        DatabaseConfig,
        create_executor,
    )

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
    from seatunnel_agent.agents.data.data_skew.sections import (
        PROBE_HEAD_RE as _PROBE_HEAD_RE,
    )
    from seatunnel_agent.agents.data.data_skew.sections import (
        remove_section as _remove_section,
    )

    section = render_probe_section([_fake_result()], "en")
    report = "# Report\n\nbody text\n\n" + section
    assert _remove_section(report, _PROBE_HEAD_RE) == "# Report\n\nbody text"
    # A mid-sentence quote of the heading must NOT truncate the report.
    quoted = "# Report\n\nsee the ## Skew Verification (measured) section below\n"
    assert _remove_section(quoted, _PROBE_HEAD_RE) == quoted


def test_remove_section_only_touches_its_own_section():
    from seatunnel_agent.agents.data.data_skew import consistency
    from seatunnel_agent.agents.data.data_skew.sections import (
        CST_HEAD_RE as _CST_HEAD_RE,
    )
    from seatunnel_agent.agents.data.data_skew.sections import (
        PROBE_HEAD_RE as _PROBE_HEAD_RE,
    )
    from seatunnel_agent.agents.data.data_skew.sections import (
        remove_section as _remove_section,
    )

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
    from seatunnel_agent.agents.data.data_skew.agent import DataSkewAgent
    from seatunnel_agent.common.config import Settings

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

from seatunnel_agent.agents.data.data_skew.probe import (
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

from seatunnel_agent.agents.data.data_skew.consistency import (
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
    from seatunnel_agent.agents.data.data_skew.probe import ProbeCache

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
    assert '/*+ SKEWJOIN(orders(user_id)(("hot")("b"))) */' in block


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
    from seatunnel_agent.agents.data.data_skew.agent import static_skew_report
    from seatunnel_agent.agents.data.data_skew.history import SkewHistory

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
    from seatunnel_agent.agents.data.data_skew.history import SkewHistory

    assert SkewHistory(log_dir=tmp_path / "nope").recent() == []


def test_default_history_env_override(tmp_path, monkeypatch):
    from seatunnel_agent.agents.data.data_skew.history import default_history

    target = tmp_path / "isolated" / "hist.jsonl"
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH", str(target))
    h = default_history()
    assert h.log_file == target


# ---------------------------------------------------------------------------
# MCP tool functions (no mcp package needed)
# ---------------------------------------------------------------------------

def test_mcp_skew_check(tmp_path, monkeypatch):
    from seatunnel_agent.agents.data.data_skew.mcp_server import build_tool_functions

    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    fns = build_tool_functions()
    out = fns["skew_check"]("SELECT count(distinct uid) FROM t")
    assert "数据倾斜分析报告" in out and "COUNT(DISTINCT)" in out
    out_en = fns["skew_check"]("SELECT count(distinct uid) FROM t", lang="en")
    assert "Data Skew Analysis Report" in out_en
    assert "不能为空" in fns["skew_check"]("   ")
    # history got both analyses
    from seatunnel_agent.agents.data.data_skew.history import default_history
    assert len(default_history().recent()) == 2


def test_mcp_skew_check_file(tmp_path, monkeypatch):
    from seatunnel_agent.agents.data.data_skew.mcp_server import build_tool_functions

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
    from seatunnel_agent.agents.data.data_skew.history import default_history
    recs = default_history().recent()
    assert len(recs) == 1 and recs[0]["source"] == "cli"


# ---------------------------------------------------------------------------
# probe: window/distinct targets and rewrite templates
# ---------------------------------------------------------------------------

def test_window_partition_key_probed():
    sql = ("SELECT uid, row_number() OVER (PARTITION BY city ORDER BY ts) rn "
           "FROM dw.events")
    targets = extract_probe_targets(sql)
    assert ("dw.events", "city", "window_key") in [
        (t.table, t.column, t.reason) for t in targets]


def test_select_distinct_leading_column_probed():
    sql = "SELECT DISTINCT city, uid FROM dw.events"
    targets = extract_probe_targets(sql)
    kinds = [(t.table, t.column, t.reason) for t in targets]
    assert ("dw.events", "city", "distinct_key") in kinds
    # only the leading column is probed
    assert ("dw.events", "uid", "distinct_key") not in kinds


def test_select_distinct_function_head_not_probed():
    sql = "SELECT DISTINCT upper(city), uid FROM dw.events"
    assert not [t for t in extract_probe_targets(sql)
                if t.reason == "distinct_key"]


def test_rewrite_templates_hot_join_and_two_stage():
    from seatunnel_agent.agents.data.data_skew.probe import render_rewrite_templates

    join = _fake_result()  # confirmed join_key, hot values hot/b
    grp = ProbeResult(target=ProbeTarget("dw.ev", "city", "group_key"))
    grp.total, grp.top = 100, [("bj", 40), ("sh", 5)]
    out = render_rewrite_templates([join, grp], "zh")
    assert "改写模板" in out
    assert "UNION ALL" in out and 'IN ("hot", "b")' in out
    assert "CAST(rand() * " in out and "GROUP BY city" in out
    out_en = render_rewrite_templates([join], "en")
    assert "hot-key isolation" in out_en


def test_rewrite_templates_count_distinct_and_null_join():
    from seatunnel_agent.agents.data.data_skew.probe import render_rewrite_templates

    cd = ProbeResult(target=ProbeTarget("dw.log", "uid", "count_distinct"))
    cd.total, cd.top = 100, [("u1", 30)]
    nul = ProbeResult(target=ProbeTarget("dw.o", "k", "join_key"))
    nul.total, nul.null_count, nul.top = 100, 30, []
    out = render_rewrite_templates([cd, nul], "zh")
    assert "GROUP BY uid" in out and "两阶段去重计数" in out
    assert "IS NOT NULL" in out and "NULL 键拆分" in out


def test_rewrite_templates_empty_when_nothing_confirmed():
    from seatunnel_agent.agents.data.data_skew.probe import render_rewrite_templates

    assert render_rewrite_templates([_fake_result("ok")], "zh") == ""


# ---------------------------------------------------------------------------
# consistency: per-column aggregate compare for large results
# ---------------------------------------------------------------------------

def test_consistency_agg_match_on_large_result(tmp_path):
    from seatunnel_agent.agents.data.data_skew.consistency import (
        check_consistency,
        render_consistency_section,
    )

    setup = ("CREATE TABLE big (k TEXT, v INTEGER); INSERT INTO big VALUES "
             + ",".join(f"('k{i}', {i})" for i in range(10)) + ";")
    ex = _sqlite_executor(tmp_path, setup)
    res = check_consistency(ex, "SELECT k, v FROM big",
                            "SELECT k, v FROM big ORDER BY v", max_rows=2)
    assert res.orig_count == res.opt_count == 10
    assert not res.rows_compared
    assert res.agg_compared and res.agg_match and res.agg_cols == 2
    sec = render_consistency_section(res, "zh")
    assert "逐列一致" in sec
    assert "COUNT / COUNT DISTINCT / MIN / MAX" in render_consistency_section(res, "en")


def test_consistency_agg_differ_detected(tmp_path):
    from seatunnel_agent.agents.data.data_skew.consistency import check_consistency

    setup = ("CREATE TABLE big (k TEXT, v INTEGER); INSERT INTO big VALUES "
             + ",".join(f"('k{i}', {i})" for i in range(10)) + ";")
    ex = _sqlite_executor(tmp_path, setup)
    # same row count, different v values
    res = check_consistency(ex, "SELECT k, v FROM big",
                            "SELECT k, v + 1 AS v FROM big", max_rows=2)
    assert res.agg_compared and not res.agg_match


def test_consistency_agg_skipped_on_renamed_columns(tmp_path):
    from seatunnel_agent.agents.data.data_skew.consistency import check_consistency

    setup = ("CREATE TABLE big (k TEXT, v INTEGER); INSERT INTO big VALUES "
             + ",".join(f"('k{i}', {i})" for i in range(10)) + ";")
    ex = _sqlite_executor(tmp_path, setup)
    res = check_consistency(ex, "SELECT k, v FROM big",
                            "SELECT k AS kk, v AS vv FROM big", max_rows=2)
    # no shared simple columns -> falls back to the count-only verdict
    assert res.orig_count == res.opt_count == 10
    assert not res.error


# ---------------------------------------------------------------------------
# REST API (/api/skew)
# ---------------------------------------------------------------------------

def _api_client(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.data_skew.api import router

    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_skew_check(tmp_path, monkeypatch):
    client = _api_client(tmp_path, monkeypatch)
    resp = client.post("/api/skew/check", json={
        "sql": "SELECT count(distinct uid) FROM t", "lang": "en"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["counts"]["medium"] == 1
    assert "Data Skew Analysis Report" in data["report"]
    assert data["findings"][0]["severity"] == "medium"
    # history logged with source=api
    from seatunnel_agent.agents.data.data_skew.history import default_history
    assert default_history().recent()[0]["source"] == "api"


def test_api_skew_check_rejects_unknown_dialect(tmp_path, monkeypatch):
    client = _api_client(tmp_path, monkeypatch)
    resp = client.post("/api/skew/check", json={
        "sql": "SELECT 1", "dialect": "oracle"})
    assert resp.status_code == 400
    assert "oracle" in resp.json()["detail"]


def test_api_skew_health(tmp_path, monkeypatch):
    client = _api_client(tmp_path, monkeypatch)
    assert client.get("/api/skew/health").json()["status"] == "ok"


# ---------------------------------------------------------------------------
# CLI: seatunnel-agent skew-stats
# ---------------------------------------------------------------------------

def test_cli_skew_stats(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    runner = CliRunner()
    empty = runner.invoke(cli, ["skew-stats"])
    assert empty.exit_code == 0 and "还没有" in empty.output
    runner.invoke(cli, ["skew", "-s", "SELECT count(distinct uid) FROM t"])
    runner.invoke(cli, ["skew", "-s", "SELECT 1"])
    res = runner.invoke(cli, ["skew-stats"])
    assert res.exit_code == 0, res.output
    assert "共 2 次" in res.output
    assert "cli×2" in res.output.replace(" ", "")


# ---------------------------------------------------------------------------
# probe: storage/modeling-layer advice
# ---------------------------------------------------------------------------

from seatunnel_agent.agents.data.data_skew.probe import (
    render_storage_advice,
)


def _hot_result(table="orders", col="region", total=100, hot=80, nulls=0):
    r = ProbeResult(target=ProbeTarget(table, col, "group_key"),
                    total=total, null_count=nulls)
    if hot:
        r.top = [("CN", hot), ("US", total - hot - nulls)]
    return r


def test_storage_advice_hot_key():
    md = render_storage_advice([_hot_result()], "en")
    assert "orders.region" in md
    assert "partition_column" in md
    assert "80.0%" in md
    zh = render_storage_advice([_hot_result()], "zh")
    assert "orders.region" in zh
    assert "80.0%" in zh


def test_storage_advice_null_heavy():
    r = ProbeResult(target=ProbeTarget("t", "k", "join_key"),
                    total=100, null_count=30)
    r.top = [("NULL", 30), ("a", 10)]
    # NULL confirmed but top1 (NULL bucket) also >= 20% → hot branch wins;
    # use a mildly-hot top1 with heavy NULLs instead
    r2 = ProbeResult(target=ProbeTarget("t", "k", "join_key"),
                     total=1000, null_count=150)
    r2.top = [("a", 100), ("b", 90)]
    md = render_storage_advice([r2], "en")
    assert "NULL ratio 15.0%" in md
    zh = render_storage_advice([r2], "zh")
    assert "15.0%" in zh


def test_storage_advice_balanced_columns_silent():
    r = ProbeResult(target=ProbeTarget("t", "id", "join_key"),
                    total=1000, null_count=0)
    r.top = [("1", 10), ("2", 9)]
    assert render_storage_advice([r], "en") == ""


def test_storage_advice_in_probe_section():
    md = render_probe_section([_hot_result()], "zh", dialect="spark")
    assert "存储/建模层建议" in md


# ---------------------------------------------------------------------------
# SeaTunnel split-key check
# ---------------------------------------------------------------------------

from seatunnel_agent.agents.data.data_skew.splitkey import (
    SourceSpec,
    SplitKeyError,
    SplitStat,
    apply_split_key,
    parse_seatunnel_source,
    parse_seatunnel_sources,
    pick_best_key,
    rank_candidates,
    render_splitkey_multi,
    render_splitkey_section,
    run_split_key_multi,
)

_CONF_BLOCK = """
env { parallelism = 4 }
source {
  Jdbc {
    url = "jdbc:mysql://h:3306/shop"
    table_name = "orders"
    partition_column = "region"
    partition_num = 8
  }
}
sink { Console {} }
"""

_CONF_LIST = """
source = [
  { plugin_name = "Jdbc", query = "select * from shop.orders where dt='x'" }
]
sink { Console {} }
"""


def test_parse_source_block_form():
    spec = parse_seatunnel_source(_CONF_BLOCK)
    assert spec.plugin == "Jdbc"
    assert spec.table == "orders"
    assert spec.partition_column == "region"
    assert spec.partition_num == 8
    assert spec.parallelism == 4
    assert spec.tasks == 8


def test_parse_source_list_form_table_from_query():
    spec = parse_seatunnel_source(_CONF_LIST)
    assert spec.plugin == "Jdbc"
    assert spec.table == "shop.orders"
    assert spec.partition_column == ""
    assert spec.tasks == 2  # nothing configured → floor of 2


_CONF_CDC = """
env { parallelism = 2 }
source {
  MySQL-CDC {
    hostname = "localhost"
    database-name = "test_db"
    table-name = "users"
    scan.incremental.snapshot.chunk.key-column = "id"
  }
}
sink { Console {} }
"""


def test_parse_source_cdc_hyphenated():
    """CDC connectors use hyphenated options and split db from table."""
    spec = parse_seatunnel_source(_CONF_CDC)
    assert spec.plugin == "MySQL-CDC"
    assert spec.table == "test_db.users"
    # the incremental-snapshot chunk key is the CDC split key
    assert spec.partition_column == "id"
    assert spec.split_option == "scan.incremental.snapshot.chunk.key-column"
    assert spec.tasks == 2


def test_parse_source_cdc_plural_list_options():
    spec = parse_seatunnel_source("""
source = [{ plugin_name = "MySQL-CDC",
            database-names = ["shop"],
            table-names = ["shop.orders", "shop.users"] }]
sink {}
""")
    assert spec.plugin == "MySQL-CDC"
    # first list entry, already db-qualified -> no double prefix
    assert spec.table == "shop.orders"
    assert spec.partition_column == ""


def test_parse_repo_demo_conf():
    """The repo's own CDC demo config must parse (regression: spk_no_table)."""
    from pathlib import Path as _P

    text = (_P(__file__).parent.parent / "examples"
            / "mysql_to_console.conf").read_text(encoding="utf-8")
    spec = parse_seatunnel_source(text)
    assert spec.plugin == "MySQL-CDC"
    assert spec.table == "test_db.users"


def test_parse_source_errors():
    import pytest

    with pytest.raises(SplitKeyError) as e1:
        parse_seatunnel_source("source { Jdbc {{{")
    assert e1.value.key == "spk_parse_fail"
    with pytest.raises(SplitKeyError) as e2:
        parse_seatunnel_source("sink { Console {} }")
    assert e2.value.key == "spk_no_source"
    with pytest.raises(SplitKeyError) as e3:
        parse_seatunnel_source(
            'source { Jdbc { query = "select a.x from a join b" } } sink {}')
    assert e3.value.key == "spk_no_table"


def test_splitstat_verdicts():
    tasks = 4
    good = SplitStat("id", total=10000, ndv=10000, top1_count=1)
    assert good.verdict(tasks) == "good"
    bad = SplitStat("region", total=100, ndv=100, top1_count=80)
    assert bad.verdict(tasks) == "bad"
    low = SplitStat("region", total=100, ndv=5, top1_count=3)
    assert low.verdict(tasks) == "low_ndv"
    nul = SplitStat("k", total=100, ndv=100, null_count=30)
    assert nul.verdict(tasks) == "null"
    err = SplitStat("k", error="boom")
    assert err.verdict(tasks) == "error"
    assert SplitStat("k").verdict(tasks) == "empty"


def test_rank_candidates_orders_good_first():
    tasks = 2
    bad = SplitStat("region", total=100, ndv=100, top1_count=80)
    good = SplitStat("id", total=100, ndv=100, top1_count=2)
    mild = SplitStat("uid", total=100, ndv=100, top1_count=10)
    ranked = rank_candidates([bad, mild, good], tasks)
    assert [s.column for s in ranked] == ["id", "uid", "region"]


def test_render_splitkey_section_error_row():
    spec = SourceSpec(plugin="Jdbc", table="t", partition_column="k")
    stat = SplitStat("k", error="table not found | details")
    md = render_splitkey_section(spec, stat, [], "en")
    assert "table not found" in md
    assert r"\|" in md  # pipe escaped for the markdown table


# ---------------------------------------------------------------------------
# split-key: re-check comparison + write-back (the loop-closing half)
# ---------------------------------------------------------------------------

def _prev_rec(verdict: str, key: str = "region") -> dict:
    return {"timestamp": "2026-09-29T10:00:00+00:00",
            "splitkey": {"table": "orders", "partition_column": key,
                         "key_verdict": verdict, "candidates": 3}}


def test_recheck_line_states():
    spec = SourceSpec(plugin="Jdbc", table="orders", partition_column="id",
                      partition_num=4)
    good = SplitStat("id", total=100, ndv=100, top1_count=1)
    bad = SplitStat("id", total=100, ndv=50, top1_count=80)

    # bad -> good: the fix landed, loop closed
    md = render_splitkey_section(spec, good, [], "zh",
                                 previous=_prev_rec("bad"))
    assert "复测对比" in md and "已解决" in md and "`region`" in md

    # good -> bad: regression
    md = render_splitkey_section(spec, bad, [], "zh",
                                 previous=_prev_rec("good", key="id"))
    assert "退化" in md

    # bad -> bad: still unresolved
    md = render_splitkey_section(spec, bad, [], "zh",
                                 previous=_prev_rec("bad"))
    assert "仍未解决" in md

    # good -> good: quiet, and first run renders no comparison at all
    md = render_splitkey_section(spec, good, [], "zh",
                                 previous=_prev_rec("good", key="id"))
    assert "复测对比" not in md
    md = render_splitkey_section(spec, good, [], "zh", previous=None)
    assert "复测对比" not in md


def test_apply_split_key_replace_multiline():
    conf = (
        "source {\n"
        "  Jdbc {\n"
        '    table_name = "orders"\n'
        '    partition_column = "region"\n'
        "    partition_num = 4\n"
        "  }\n"
        "}\n"
        "sink { Console {} }\n"
    )
    spec = parse_seatunnel_source(conf)
    out = apply_split_key(conf, spec, "id", partition_num=8)
    assert 'partition_column = "id"' in out
    assert "partition_num = 8" in out
    assert "region" not in out
    assert 'table_name = "orders"' in out  # formatting preserved
    # the rewritten config round-trips through the parser
    spec2 = parse_seatunnel_source(out)
    assert spec2.partition_column == "id"
    assert spec2.partition_num == 8


def test_apply_split_key_oneline_replace_and_insert():
    # replace on a single-line source, partition_num appended inline
    conf = ('source { Jdbc { table_name = "orders", '
            'partition_column = "region" } } sink {}')
    spec = parse_seatunnel_source(conf)
    out = apply_split_key(conf, spec, "id", partition_num=2)
    spec2 = parse_seatunnel_source(out)
    assert spec2.partition_column == "id"
    assert spec2.partition_num == 2

    # no key configured: inserted inline after the table option
    conf = 'source { Jdbc { table_name = "orders" } } sink {}'
    spec = parse_seatunnel_source(conf)
    out = apply_split_key(conf, spec, "id", partition_num=2)
    spec2 = parse_seatunnel_source(out)
    assert spec2.partition_column == "id"
    assert spec2.partition_num == 2


def test_apply_split_key_skips_comments():
    conf = (
        "source {\n"
        "  Jdbc {\n"
        '    table_name = "orders"\n'
        '    # partition_column = "old_commented_out"\n'
        '    partition_column = "region"\n'
        "  }\n"
        "}\n"
    )
    spec = parse_seatunnel_source(conf)
    out = apply_split_key(conf, spec, "id")
    assert '# partition_column = "old_commented_out"' in out  # untouched
    assert 'partition_column = "id"' in out
    assert '"region"' not in out


def test_apply_split_key_cdc_chunk_key():
    spec = parse_seatunnel_source(_CONF_CDC)
    out = apply_split_key(_CONF_CDC, spec, "user_id")
    assert 'scan.incremental.snapshot.chunk.key-column = "user_id"' in out
    assert "partition_num" not in out  # CDC option carries no partition_num
    assert parse_seatunnel_source(out).partition_column == "user_id"


def test_apply_split_key_no_anchor():
    import pytest

    conf = 'source { Jdbc { query = "select a.x from a join b" } } sink {}'
    spec = SourceSpec(plugin="Jdbc", table="a")  # as if resolved elsewhere
    # query anchor exists -> inline insert works even for query sources
    out = apply_split_key(conf, spec, "id")
    assert 'partition_column = "id"' in out
    # nothing to anchor on at all
    with pytest.raises(SplitKeyError) as e:
        apply_split_key("env { parallelism = 2 }", spec, "id")
    assert e.value.key == "spk_apply_fail"


def test_pick_best_key():
    spec = SourceSpec(plugin="Jdbc", table="orders",
                      partition_column="region", parallelism=2)
    good = SplitStat("id", total=100, ndv=100, top1_count=1)
    bad = SplitStat("region", total=100, ndv=50, top1_count=80)
    assert pick_best_key(spec, bad, [good]).column == "id"
    assert pick_best_key(spec, good, [bad]).column == "id"   # keep configured
    assert pick_best_key(spec, bad, [bad]) is None


# ---------------------------------------------------------------------------
# split-key: approx NDV, history, MCP tools, CLI
# ---------------------------------------------------------------------------

def test_stats_sql_approx_ndv_per_engine():
    from seatunnel_agent.agents.data.data_skew.splitkey import _stats_sql

    assert "approx_count_distinct(c)" in _stats_sql("c", "t", "sparksql")
    assert "uniq(c)" in _stats_sql("c", "t", "clickhouse")
    assert "ndv(c)" in _stats_sql("c", "t", "doris")
    for exact in ("mysql", "hive", "postgresql", "sqlite", ""):
        assert "COUNT(DISTINCT c)" in _stats_sql("c", "t", exact)


def test_history_log_splitkey(tmp_path):
    from seatunnel_agent.agents.data.data_skew.history import SkewHistory

    h = SkewHistory(log_dir=tmp_path)
    h.log_splitkey("orders", "region", "bad", candidates=3, source="cli")
    h.log_splitkey("orders", "", "none", candidates=2)
    h.log_splitkey("t2", "id", "good", candidates=1, source="mcp")
    recs = h.recent(10)
    assert [r["verdict"] for r in recs] == ["clean", "medium", "high"]
    bad = recs[2]
    assert bad["mode"] == "splitkey"
    assert bad["counts"] == {"high": 1, "medium": 0, "low": 0}
    assert bad["splitkey"] == {"table": "orders", "partition_column": "region",
                               "key_verdict": "bad", "candidates": 3}
    assert "orders" in bad["sql"]  # readable in the history panel


def test_history_last_runtime(tmp_path):
    from seatunnel_agent.agents.data.data_skew.history import SkewHistory

    h = SkewHistory(log_dir=tmp_path)
    assert h.last_runtime("app-1") is None
    h.log_runtime("app-1", stages=5, confirmed=2, suspect=1)
    h.log_runtime("app-2", stages=3, confirmed=0, suspect=0)
    h.log_runtime("app-1", stages=5, confirmed=0, suspect=1)
    rec = h.last_runtime("app-1")
    assert rec["runtime"]["confirmed"] == 0    # latest wins
    assert h.last_runtime("") is None
    assert h.last_runtime("nope") is None


def test_runtime_recheck_line_i18n():
    from seatunnel_agent.agents.data.data_skew.i18n import DSK_I18N

    for key in ("rt_recheck_better", "rt_recheck_worse", "rt_recheck_same"):
        assert key in DSK_I18N["en"] and key in DSK_I18N["zh"]


def test_history_last_splitkey(tmp_path):
    from seatunnel_agent.agents.data.data_skew.history import SkewHistory

    h = SkewHistory(log_dir=tmp_path)
    assert h.last_splitkey("orders") is None       # empty history
    h.log_splitkey("orders", "region", "bad", candidates=3)
    h.log_splitkey("t2", "id", "good", candidates=1)
    h.log_splitkey("orders", "id", "good", candidates=2)
    rec = h.last_splitkey("orders")
    assert rec["splitkey"]["partition_column"] == "id"   # latest wins
    assert rec["splitkey"]["key_verdict"] == "good"
    assert h.last_splitkey("nope") is None
    assert h.last_splitkey("") is None


_SPLITKEY_CONF = """
env { parallelism = 2 }
source { Jdbc { table_name = "orders", partition_column = "region" } }
sink { Console {} }
"""


def _make_orders_db(tmp_path):
    """A sqlite DB with a skewed region column and a uniform id."""
    import sqlite3

    db = tmp_path / "spk.db"
    conn = sqlite3.connect(db)
    rows = ",".join(
        f"({i}, '{'CN' if i <= 80 else 'US'}', {i * 10})" for i in range(1, 101))
    conn.executescript(
        "CREATE TABLE orders (id INTEGER, region TEXT, amount INTEGER);"
        f"INSERT INTO orders VALUES {rows};")
    conn.commit()
    conn.close()
    return db


def test_mcp_skew_drift(monkeypatch, tmp_path):
    from seatunnel_agent.agents.data.data_skew.history import default_history
    from seatunnel_agent.agents.data.data_skew.mcp_server import (
        build_tool_functions,
    )

    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    fns = build_tool_functions()
    # empty history → pointer to skew_split_key patrols
    assert "skew-splitkey" in fns["skew_drift"]()

    h = default_history()
    for top1 in (10.0, 14.0, 28.0):
        h.log_splitkey("orders", "id", "good", top1_pct=top1)
    out = fns["skew_drift"]("orders", lang="en")
    assert "drifted" in out and "top1_pct" in out
    # sweep + zh; the patrol lands in history with source=mcp
    out_zh = fns["skew_drift"]()
    assert "漂移" in out_zh
    rec = default_history().recent(1)[0]
    assert rec["mode"] == "drift" and rec["source"] == "mcp"
    # no-db profile still exposes the (history-only) drift tool
    assert "skew_drift" in build_tool_functions(include_db=False)


def test_mcp_split_key_validation(monkeypatch, tmp_path):
    from seatunnel_agent.agents.data.data_skew.mcp_server import build_tool_functions

    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    fns = build_tool_functions()
    assert set(fns) == {"skew_check", "skew_check_file",
                        "skew_runtime_eventlog", "skew_runtime_history",
                        "skew_drift", "skew_split_key", "skew_split_key_file",
                        "skew_split_key_apply"}
    spk = fns["skew_split_key"]
    assert "不能为空" in spk("")
    assert "ds_type" in spk(_SPLITKEY_CONF, ds_type="oracle")
    monkeypatch.delenv("MYSQL_HOST", raising=False)
    assert ".env" in spk(_SPLITKEY_CONF, ds_type="mysql")


def test_mcp_split_key_end_to_end(monkeypatch, tmp_path):
    from seatunnel_agent.agents.data.data_skew.history import default_history
    from seatunnel_agent.agents.data.data_skew.mcp_server import build_tool_functions
    from seatunnel_agent.agents.data.text2sql.executor import base as exec_base

    db = _make_orders_db(tmp_path)
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    monkeypatch.setattr(
        exec_base, "config_from_env",
        lambda ds: exec_base.DatabaseConfig(
            ds_type="sqlite", host="", port=0, database=str(db)))
    fns = build_tool_functions()
    md = fns["skew_split_key"](_SPLITKEY_CONF, ds_type="sqlite", lang="zh")
    assert "## SeaTunnel 分片键体检" in md
    assert 'partition_column = "id"' in md  # skewed region → id promoted
    rec = default_history().recent(1)[0]
    assert rec["mode"] == "splitkey" and rec["source"] == "mcp"
    assert rec["splitkey"]["key_verdict"] in ("bad", "low_ndv")

    # file variant + missing file
    conf_file = tmp_path / "job.conf"
    conf_file.write_text(_SPLITKEY_CONF, encoding="utf-8")
    md2 = fns["skew_split_key_file"](str(conf_file), ds_type="sqlite")
    assert "## SeaTunnel 分片键体检" in md2
    assert "读取文件失败" in fns["skew_split_key_file"](str(tmp_path / "nope.conf"))


def test_cli_skew_splitkey(monkeypatch, tmp_path):
    from click.testing import CliRunner

    from seatunnel_agent.agents.data.text2sql.executor import base as exec_base
    from seatunnel_agent.cli import cli

    db = _make_orders_db(tmp_path)
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    monkeypatch.setattr(
        exec_base, "config_from_env",
        lambda ds: exec_base.DatabaseConfig(
            ds_type="sqlite", host="", port=0, database=str(db)))
    conf_file = tmp_path / "job.conf"
    conf_file.write_text(_SPLITKEY_CONF, encoding="utf-8")

    runner = CliRunner()
    res = runner.invoke(cli, ["skew-splitkey", str(conf_file), "--ds", "sqlite"])
    assert res.exit_code == 0, res.output
    assert "SeaTunnel" in res.output

    # CI gate: the configured region key measures skewed → exit 1
    gated = runner.invoke(
        cli, ["skew-splitkey", str(conf_file), "--ds", "sqlite", "--fail"])
    assert gated.exit_code == 1
    assert "检查未通过" in gated.output

    # report file output
    out = tmp_path / "spk.md"
    runner.invoke(cli, ["skew-splitkey", str(conf_file), "--ds", "sqlite",
                        "-o", str(out)])
    assert "分片键体检" in out.read_text(encoding="utf-8")


def test_cli_skew_splitkey_drift_tail(monkeypatch, tmp_path):
    """skew-splitkey ends with the drift-vs-baseline line once history
    is deep enough (same data every run → stable)."""
    from click.testing import CliRunner

    from seatunnel_agent.agents.data.text2sql.executor import base as exec_base
    from seatunnel_agent.cli import cli

    db = _make_orders_db(tmp_path)
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    monkeypatch.setattr(
        exec_base, "config_from_env",
        lambda ds: exec_base.DatabaseConfig(
            ds_type="sqlite", host="", port=0, database=str(db)))
    conf_file = tmp_path / "job.conf"
    conf_file.write_text(_SPLITKEY_CONF, encoding="utf-8")

    runner = CliRunner()
    first = runner.invoke(cli, ["skew-splitkey", str(conf_file), "--ds", "sqlite"])
    assert first.exit_code == 0, first.output
    assert "暂无基线" in first.output          # 1 measured run: insufficient
    runner.invoke(cli, ["skew-splitkey", str(conf_file), "--ds", "sqlite"])
    third = runner.invoke(cli, ["skew-splitkey", str(conf_file), "--ds", "sqlite"])
    assert third.exit_code == 0, third.output
    assert "倾斜漂移" in third.output
    assert "相对基线稳定" in third.output       # identical data → stable


def test_cli_skew_splitkey_recovery_card(monkeypatch, tmp_path):
    """A stable measurement after a reported drift emits the recovery card
    from the splitkey patrol itself (webhook included)."""
    from click.testing import CliRunner

    from seatunnel_agent.agents.data.data_skew import notify
    from seatunnel_agent.agents.data.data_skew.history import default_history
    from seatunnel_agent.agents.data.text2sql.executor import base as exec_base
    from seatunnel_agent.cli import cli

    db = _make_orders_db(tmp_path)
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    monkeypatch.setattr(
        exec_base, "config_from_env",
        lambda ds: exec_base.DatabaseConfig(
            ds_type="sqlite", host="", port=0, database=str(db)))
    h = default_history()
    # steady history at the same level the live probe will measure (~80%),
    # plus a previously reported drift → this patrol is a recovery
    for _ in range(3):
        h.log_splitkey("orders", "region", "bad", top1_pct=80.0)
    h.log_drift("orders", "drift", ["top1_pct"], deltas={"top1_pct": 20.0})
    posted: list[dict] = []
    monkeypatch.setattr(notify, "post_webhook",
                        lambda url, payload: (posted.append(payload)
                                              or (True, "200")))
    conf_file = tmp_path / "job.conf"
    conf_file.write_text(_SPLITKEY_CONF, encoding="utf-8")

    res = CliRunner().invoke(cli, ["skew-splitkey", str(conf_file),
                                   "--ds", "sqlite",
                                   "--webhook", "http://hook/x"])
    assert res.exit_code == 0, res.output
    assert "倾斜漂移恢复" in res.output
    assert posted and "恢复" in posted[0]["text"]
    assert posted[0]["drift_tables"] == ["orders"]
    rec = [r for r in default_history().recent(5) if r.get("mode") == "drift"][0]
    assert rec["drift"]["drift_verdict"] == "stable"


def test_cli_skew_splitkey_apply_closes_loop(monkeypatch, tmp_path):
    """check → --apply writes the fix back → re-check reports it resolved."""
    from click.testing import CliRunner

    from seatunnel_agent.agents.data.text2sql.executor import base as exec_base
    from seatunnel_agent.cli import cli

    db = _make_orders_db(tmp_path)
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    monkeypatch.setattr(
        exec_base, "config_from_env",
        lambda ds: exec_base.DatabaseConfig(
            ds_type="sqlite", host="", port=0, database=str(db)))
    conf_file = tmp_path / "job.conf"
    conf_file.write_text(_SPLITKEY_CONF, encoding="utf-8")

    runner = CliRunner()
    # 1. region is skewed → --apply rewrites the config (backup kept)
    res = runner.invoke(cli, ["skew-splitkey", str(conf_file),
                              "--ds", "sqlite", "--apply"])
    assert res.exit_code == 0, res.output
    assert "已把分片键写回配置" in res.output
    new_conf = conf_file.read_text(encoding="utf-8")
    assert 'partition_column = "id"' in new_conf
    bak = tmp_path / "job.conf.bak"
    assert 'partition_column = "region"' in bak.read_text(encoding="utf-8")

    # 2. re-check the rewritten config: the comparison line closes the loop
    res2 = runner.invoke(cli, ["skew-splitkey", str(conf_file),
                               "--ds", "sqlite", "--fail"])
    assert res2.exit_code == 0, res2.output   # CI gate now passes
    assert "复测对比" in res2.output
    assert "已解决" in res2.output

    # 3. good key + --apply again: nothing to write back
    res3 = runner.invoke(cli, ["skew-splitkey", str(conf_file),
                               "--ds", "sqlite", "--apply"])
    assert res3.exit_code == 0
    assert "没有可写回" in res3.output


# ---------------------------------------------------------------------------
# split-key: multi-source configs
# ---------------------------------------------------------------------------

_CONF_MULTI = """
env { parallelism = 2 }
source = [
  { plugin_name = "Jdbc", table_name = "orders", partition_column = "region" },
  { plugin_name = "Jdbc", table_name = "users", partition_column = "uid" }
]
sink { Console {} }
"""


def _make_two_table_db(tmp_path):
    """orders (skewed region / uniform id) + users (uniform uid)."""
    import sqlite3

    db = tmp_path / "multi.db"
    conn = sqlite3.connect(db)
    orders = ",".join(
        f"({i}, '{'CN' if i <= 80 else 'US'}', {i * 10})" for i in range(1, 101))
    users = ",".join(f"({i}, {i % 7})" for i in range(1, 101))
    conn.executescript(
        "CREATE TABLE orders (id INTEGER, region TEXT, amount INTEGER);"
        f"INSERT INTO orders VALUES {orders};"
        "CREATE TABLE users (uid INTEGER, grade INTEGER);"
        f"INSERT INTO users VALUES {users};")
    conn.commit()
    conn.close()
    return db


def test_parse_sources_multi_list_form():
    specs = parse_seatunnel_sources(_CONF_MULTI)
    assert [s.table for s in specs] == ["orders", "users"]
    assert [s.partition_column for s in specs] == ["region", "uid"]
    assert all(s.parallelism == 2 for s in specs)
    # the compat single-source path still resolves the first one
    assert parse_seatunnel_source(_CONF_MULTI).table == "orders"


def test_parse_sources_skips_unresolvable_entry():
    conf = """
    source = [
      { plugin_name = "Jdbc", query = "select a.x from a join b on a.k=b.k" },
      { plugin_name = "Jdbc", table_name = "orders" }
    ]
    sink {}
    """
    specs = parse_seatunnel_sources(conf)
    assert [s.table for s in specs] == ["orders"]
    # every entry unresolvable → spk_no_table, as before
    bad = 'source = [{ plugin_name = "Jdbc", query = "select 1" }]\nsink {}'
    try:
        parse_seatunnel_sources(bad)
        raise AssertionError("expected SplitKeyError")
    except SplitKeyError as exc:
        assert exc.key == "spk_no_table"


def test_run_split_key_multi_cap_and_truncated_note(tmp_path):
    db = _make_two_table_db(tmp_path)
    from seatunnel_agent.agents.data.text2sql.executor.base import (
        DatabaseConfig,
        create_executor,
    )
    ex = create_executor(
        DatabaseConfig(ds_type="sqlite", host="", port=0, database=str(db)))

    results, total = run_split_key_multi(
        ex, _CONF_MULTI, ds_type="sqlite", max_sources=1)
    assert total == 2 and len(results) == 1
    md = render_splitkey_multi(results, "zh", total=total)
    assert "仅体检前 1 个" in md
    en = render_splitkey_multi(results, "en", total=total)
    assert "first 1" in en


def test_render_splitkey_multi_single_source_unchanged():
    spec = SourceSpec(plugin="Jdbc", table="t", partition_column="k")
    stat = SplitStat("k", total=100, ndv=50, top1_count=3)
    single = render_splitkey_multi([(spec, stat, [])], "en", total=1)
    assert single == render_splitkey_section(spec, stat, [], "en")


def test_cli_skew_splitkey_apply_refuses_multi(monkeypatch, tmp_path):
    from click.testing import CliRunner

    from seatunnel_agent.agents.data.text2sql.executor import base as exec_base
    from seatunnel_agent.cli import cli

    db = _make_two_table_db(tmp_path)
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    monkeypatch.setattr(
        exec_base, "config_from_env",
        lambda ds: exec_base.DatabaseConfig(
            ds_type="sqlite", host="", port=0, database=str(db)))
    conf_file = tmp_path / "multi.conf"
    conf_file.write_text(_CONF_MULTI, encoding="utf-8")

    runner = CliRunner()
    # plain check works and reports both sources
    res = runner.invoke(cli, ["skew-splitkey", str(conf_file), "--ds", "sqlite"])
    assert res.exit_code == 0, res.output
    assert "orders" in res.output and "users" in res.output

    # --apply refuses: a text edit could hit the wrong source block
    res2 = runner.invoke(cli, ["skew-splitkey", str(conf_file),
                               "--ds", "sqlite", "--apply"])
    assert res2.exit_code != 0
    assert "仅支持单 source" in res2.output
    # nothing was written
    assert conf_file.read_text(encoding="utf-8") == _CONF_MULTI
    assert not (tmp_path / "multi.conf.bak").exists()


def test_mcp_split_key_apply(monkeypatch, tmp_path):
    from seatunnel_agent.agents.data.data_skew.mcp_server import build_tool_functions
    from seatunnel_agent.agents.data.text2sql.executor import base as exec_base

    db = _make_two_table_db(tmp_path)
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    monkeypatch.setattr(
        exec_base, "config_from_env",
        lambda ds: exec_base.DatabaseConfig(
            ds_type="sqlite", host="", port=0, database=str(db)))
    fns = build_tool_functions()
    apply_fn = fns["skew_split_key_apply"]

    # skewed region → patched config text with the measured key written in
    out = apply_fn(_SPLITKEY_CONF, ds_type="sqlite")
    assert out.startswith("# split key:")
    assert 'partition_column = "id"' in out
    assert 'table_name = "orders"' in out  # rest of the config intact

    # already-good key → nothing to write back
    good = out.split("\n", 1)[1]
    assert "没有可写回" in apply_fn(good, ds_type="sqlite")

    # multi-source config → refused
    assert "仅支持单 source" in apply_fn(_CONF_MULTI, ds_type="sqlite")

    # validation mirrors skew_split_key
    assert "不能为空" in apply_fn("")
    assert "ds_type" in apply_fn(_SPLITKEY_CONF, ds_type="oracle")


# ---------------------------------------------------------------------------
# runtime diagnosis (Spark task metrics)
# ---------------------------------------------------------------------------

from seatunnel_agent.agents.data.data_skew.runtime import (
    MIN_TASKS,
    RuntimeSkewError,
    StageSkew,
    analyze_history_server,
    parse_eventlog,
    render_runtime_section,
)


def _eventlog_events() -> list:
    """Stage 1: one 60s straggler vs ~2s median (confirmed, mapped to SQL);
    stage 2: balanced. Plus a failed task and a torn line to ignore."""
    events: list = [
        {"Event": "SparkListenerApplicationStart", "App Name": "etl-daily"},
        {"Event": ("org.apache.spark.sql.execution.ui."
                   "SparkListenerSQLExecutionStart"),
         "executionId": 0,
         "description": "insert overwrite table dws.orders select ..."},
        {"Event": "SparkListenerJobStart", "Job ID": 0, "Stage IDs": [1, 2],
         "Properties": {"spark.sql.execution.id": "0"}},
        {"Event": "SparkListenerStageCompleted",
         "Stage Info": {"Stage ID": 1,
                        "Stage Name": "Exchange hashpartitioning(k#1, 200)"}},
        {"Event": "SparkListenerStageCompleted",
         "Stage Info": {"Stage ID": 2, "Stage Name": "Scan parquet"}},
    ]

    def task(sid: int, dur_ms: int, shuf: int = 0, failed: bool = False):
        return {"Event": "SparkListenerTaskEnd", "Stage ID": sid,
                "Task Info": {"Launch Time": 0, "Finish Time": dur_ms,
                              "Failed": failed},
                "Task Metrics": {"Shuffle Read Metrics": {
                    "Remote Bytes Read": shuf, "Local Bytes Read": 0}}}

    for d in (2000, 2000, 2500, 60_000):
        events.append(task(1, d, shuf=1024))
    for d in (3000, 3100, 2900, 3000):
        events.append(task(2, d))
    events.append(task(2, 999_999, failed=True))  # must be ignored
    return events


def _write_eventlog(path, events=None) -> None:
    import json as _json

    lines = [_json.dumps(e) for e in (events or _eventlog_events())]
    lines.insert(3, "{torn json line")  # parser must skip it
    path.write_text("\n".join(lines), encoding="utf-8")


def test_runtime_parse_eventlog(tmp_path):
    log = tmp_path / "app-123"
    _write_eventlog(log)
    stages, label = parse_eventlog(log)
    assert label == "etl-daily"
    assert [s.stage_id for s in stages] == [1, 2]  # worst first
    s1, s2 = stages
    assert s1.verdict() == "confirmed"
    assert s1.tasks == 4 and s1.dur_max == 60_000 and s1.dur_p50 == 2250
    assert "dws.orders" in s1.sql_desc  # mapped via job start properties
    assert s2.verdict() == "ok"
    assert s2.tasks == 4  # the failed task did not count


def test_runtime_parse_eventlog_label_includes_app_id(tmp_path):
    """With an App ID present, the label disambiguates same-named apps
    so the re-check line compares against the right baseline."""
    events = [dict(e) for e in _eventlog_events()]
    for e in events:
        if e.get("Event") == "SparkListenerApplicationStart":
            e["App ID"] = "application_123"
    log = tmp_path / "app-456"
    _write_eventlog(log, events)
    _, label = parse_eventlog(log)
    assert label == "etl-daily (application_123)"


def test_runtime_parse_gz_and_rolling_dir(tmp_path):
    import gzip
    import json as _json

    events = _eventlog_events()
    gz = tmp_path / "app.gz"
    with gzip.open(gz, "wt", encoding="utf-8") as f:
        f.write("\n".join(_json.dumps(e) for e in events))
    stages, _ = parse_eventlog(gz)
    assert stages[0].verdict() == "confirmed"

    # rolling event-log directory: events_* parts read in order
    d = tmp_path / "eventlog_v2_app-1"
    d.mkdir()
    half = len(events) // 2
    (d / "events_1_app-1").write_text(
        "\n".join(_json.dumps(e) for e in events[:half]), encoding="utf-8")
    (d / "events_2_app-1").write_text(
        "\n".join(_json.dumps(e) for e in events[half:]), encoding="utf-8")
    (d / "appstatus_app-1").write_text("", encoding="utf-8")  # ignored
    stages, _ = parse_eventlog(d)
    assert stages[0].verdict() == "confirmed"

    empty = tmp_path / "empty_dir"
    empty.mkdir()
    try:
        parse_eventlog(empty)
        raise AssertionError("expected RuntimeSkewError")
    except RuntimeSkewError as exc:
        assert exc.key == "rt_read_fail"


def test_runtime_render():
    # balanced-only input → the all-ok line, no AQE block
    ok = render_runtime_section(
        [StageSkew(1, tasks=4, dur_p50=1000, dur_max=1200)], "zh")
    assert "未发现运行时倾斜信号" in ok
    assert "spark.sql.adaptive" not in ok


def test_runtime_verdict_thresholds():
    # high ratio but tiny absolute max → noise, not skew
    assert StageSkew(1, tasks=8, dur_p50=10, dur_max=200).verdict() == "ok"
    # confirmed via duration
    assert StageSkew(1, tasks=8, dur_p50=5_000,
                     dur_max=40_000).verdict() == "confirmed"
    # confirmed via shuffle bytes alone
    assert StageSkew(1, tasks=8, dur_p50=1000, dur_max=1100,
                     shuf_p50=10 << 20,
                     shuf_max=300 << 20).verdict() == "confirmed"
    # suspect band
    assert StageSkew(1, tasks=8, dur_p50=4_000,
                     dur_max=15_000).verdict() == "suspect"
    # too few tasks to judge
    assert StageSkew(1, tasks=MIN_TASKS - 1, dur_p50=1000,
                     dur_max=60_000).verdict() == "ok"


def test_runtime_history_server_fake_fetch():
    calls: list[str] = []

    def fake_fetch(url: str):
        calls.append(url)
        if url.endswith("/stages?status=COMPLETE"):
            return [
                {"stageId": 7, "attemptId": 0, "name": "Exchange",
                 "numCompleteTasks": 10, "executorRunTime": 100_000},
                {"stageId": 3, "attemptId": 0, "name": "Scan",
                 "numCompleteTasks": 10, "executorRunTime": 50_000},
            ]
        if "/stages/7/0/taskSummary" in url:
            return {"duration": [2_000.0, 90_000.0],
                    "shuffleReadMetrics": {"readBytes": [1_000.0, 2_000.0]}}
        if "/stages/3/0/taskSummary" in url:
            return {"duration": [3_000.0, 3_200.0],
                    "shuffleReadMetrics": {"readBytes": [0.0, 0.0]}}
        raise AssertionError(f"unexpected URL {url}")

    stages, label = analyze_history_server(
        "http://hs:18080/", "app-42", fetch=fake_fetch)
    assert label == "app-42"
    assert calls[0] == ("http://hs:18080/api/v1/applications/app-42"
                       "/stages?status=COMPLETE")
    assert "quantiles=0.5,1.0" in calls[1]
    assert [s.stage_id for s in stages] == [7, 3]
    assert stages[0].verdict() == "confirmed"
    assert stages[1].verdict() == "ok"

    # error paths
    try:
        analyze_history_server("http://hs:18080", "app-42",
                               fetch=lambda url: (_ for _ in ()).throw(
                                   OSError("boom")))
        raise AssertionError("expected RuntimeSkewError")
    except RuntimeSkewError as exc:
        assert exc.key == "rt_http_fail"
    try:
        analyze_history_server("http://hs:18080", "app-42",
                               fetch=lambda url: [])
        raise AssertionError("expected RuntimeSkewError")
    except RuntimeSkewError as exc:
        assert exc.key == "rt_no_stages"
    try:
        analyze_history_server("", "", fetch=fake_fetch)
        raise AssertionError("expected RuntimeSkewError")
    except RuntimeSkewError as exc:
        assert exc.key == "rt_need_url"


def test_cli_skew_runtime(monkeypatch, tmp_path):
    from click.testing import CliRunner

    from seatunnel_agent.agents.data.data_skew.history import default_history
    from seatunnel_agent.cli import cli

    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    log = tmp_path / "app-123"
    _write_eventlog(log)

    runner = CliRunner()
    res = runner.invoke(cli, ["skew-runtime", str(log)])
    assert res.exit_code == 0, res.output
    assert "运行时倾斜诊断" in res.output

    rec = default_history().recent(1)[0]
    assert rec["mode"] == "runtime" and rec["source"] == "cli"
    assert rec["runtime"]["confirmed"] == 1

    # first diagnosis has no previous run → no re-check line
    assert "复测对比" not in res.output

    # CI gate: a confirmed stage exists → exit 1; same app re-diagnosed →
    # the re-check line reports "unchanged" against the first run
    gated = runner.invoke(cli, ["skew-runtime", str(log), "--fail"])
    assert gated.exit_code == 1
    assert "复测对比" in gated.output and "无变化" in gated.output
    assert "（1 →" in gated.output   # console wraps inside the parens

    # report file + argument validation
    out = tmp_path / "rt.md"
    runner.invoke(cli, ["skew-runtime", str(log), "-o", str(out)])
    assert "运行时倾斜诊断" in out.read_text(encoding="utf-8")
    both = runner.invoke(cli, ["skew-runtime", str(log),
                               "--history", "http://hs:18080", "--app", "a"])
    assert both.exit_code != 0
    neither = runner.invoke(cli, ["skew-runtime"])
    assert neither.exit_code != 0


def test_mcp_runtime_tools(monkeypatch, tmp_path):
    from seatunnel_agent.agents.data.data_skew.history import default_history
    from seatunnel_agent.agents.data.data_skew.mcp_server import build_tool_functions

    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    log = tmp_path / "app-123"
    _write_eventlog(log)
    fns = build_tool_functions()

    md = fns["skew_runtime_eventlog"](str(log))
    assert "## 运行时倾斜诊断" in md
    rec = default_history().recent(1)[0]
    assert rec["mode"] == "runtime" and rec["source"] == "mcp"

    # missing file → readable error text, no exception
    assert "读取失败" in fns["skew_runtime_eventlog"](str(tmp_path / "nope"))
    # history variant validates its inputs the same way
    assert "History Server" in fns["skew_runtime_history"]("", "")


# ---------------------------------------------------------------------------
# split-key: directory patrol (batch mode) + metric trend / drift
# ---------------------------------------------------------------------------

from seatunnel_agent.agents.data.data_skew.splitkey import (
    _recheck_line,
    batch_counts,
    render_splitkey_batch,
    run_split_key_batch,
    scan_config_files,
)


def _patrol_dir(tmp_path):
    """configs/: skewed key, good key, no key, one unparsable file, one
    non-config file that must be ignored."""
    d = tmp_path / "configs"
    (d / "nested").mkdir(parents=True)
    (d / "a_skewed.conf").write_text(
        'env { parallelism = 2 }\n'
        'source { Jdbc { table_name = "orders", partition_column = "region" } }\n'
        'sink { Console {} }\n', encoding="utf-8")
    (d / "nested" / "b_good.config").write_text(
        'env { parallelism = 2 }\n'
        'source { Jdbc { table_name = "orders", partition_column = "id" } }\n'
        'sink { Console {} }\n', encoding="utf-8")
    (d / "c_nokey.conf").write_text(
        'source { Jdbc { table_name = "users" } }\nsink { Console {} }\n',
        encoding="utf-8")
    (d / "d_broken.conf").write_text("source {{{ not hocon", encoding="utf-8")
    (d / "readme.txt").write_text("not a config", encoding="utf-8")
    return d


def test_scan_config_files(tmp_path):
    d = _patrol_dir(tmp_path)
    names = [p.name for p in scan_config_files(str(d))]
    assert names == ["a_skewed.conf", "c_nokey.conf", "d_broken.conf",
                     "b_good.config"]  # sorted by path; txt ignored


def test_run_split_key_batch_and_render(tmp_path):
    from seatunnel_agent.agents.data.text2sql.executor.base import (
        DatabaseConfig,
        create_executor,
    )

    db = _make_two_table_db(tmp_path)
    ex = create_executor(
        DatabaseConfig(ds_type="sqlite", host="", port=0, database=str(db)))
    d = _patrol_dir(tmp_path)
    items = run_split_key_batch(ex, scan_config_files(str(d)),
                                ds_type="sqlite")
    c = batch_counts(items)
    assert c == {"files": 4, "sources": 3, "bad": 1, "none": 1, "errors": 1}
    md = render_splitkey_batch(items, "zh")
    assert "## SeaTunnel 分片键巡检" in md
    assert "1 个键倾斜" in md and "1 个解析失败" in md
    assert "`a_skewed.conf`" in md and "`id`" in md  # suggested key
    assert "未配置分片键" in md
    en = render_splitkey_batch(items, "en")
    assert "## SeaTunnel Split-Key Patrol" in en
    assert "1 skewed keys" in en


def test_cli_skew_splitkey_dir_patrol(monkeypatch, tmp_path):
    from click.testing import CliRunner

    from seatunnel_agent.agents.data.data_skew import notify
    from seatunnel_agent.agents.data.data_skew.history import default_history
    from seatunnel_agent.agents.data.text2sql.executor import base as exec_base
    from seatunnel_agent.cli import cli

    db = _make_two_table_db(tmp_path)
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    monkeypatch.setattr(
        exec_base, "config_from_env",
        lambda ds: exec_base.DatabaseConfig(
            ds_type="sqlite", host="", port=0, database=str(db)))
    posted: list[tuple[str, dict]] = []
    monkeypatch.setattr(notify, "post_webhook",
                        lambda url, payload: (posted.append((url, payload))
                                              or (True, "200")))
    d = _patrol_dir(tmp_path)

    runner = CliRunner()
    res = runner.invoke(cli, ["skew-splitkey", str(d), "--ds", "sqlite",
                              "--webhook", "http://hook.local/x"])
    assert res.exit_code == 0, res.output
    assert "分片键巡检" in res.output
    # the webhook fired with the counts and the summary markdown
    assert posted and posted[0][0] == "http://hook.local/x"
    payload = posted[0][1]
    assert payload["kind"] == "splitkey_patrol"
    assert payload["counts"]["bad"] == 1 and payload["counts"]["errors"] == 1
    assert "巡检" in payload["text"]
    assert "drift_tables" not in payload   # no drift yet → payload unchanged
    # history got one record per measured source, with metrics
    recs = [r for r in default_history().recent(10)
            if r.get("mode") == "splitkey"]
    assert len(recs) == 3
    skewed = [r for r in recs
              if (r["splitkey"].get("partition_column") == "region")]
    assert skewed and skewed[0]["splitkey"]["top1_pct"] == 80.0

    # drift tail in dir mode: seed two calmer earlier runs → the 80 % run
    # the patrol just logged counts as a top1 drift; only drifted tables print
    h = default_history()
    for top1 in (20.0, 25.0):
        h.log_splitkey("orders", "region", "good", top1_pct=top1)
    posted.clear()
    res_drift = runner.invoke(cli, ["skew-splitkey", str(d), "--ds", "sqlite",
                                    "--webhook", "http://hook.local/x"])
    assert res_drift.exit_code == 0, res_drift.output
    assert "倾斜漂移" in res_drift.output and "orders" in res_drift.output
    assert "相对基线稳定" not in res_drift.output   # stable tables stay silent
    # the drifted table rides the patrol webhook
    payload = posted[0][1]
    assert payload["drift_tables"] == ["orders"]
    assert "倾斜漂移" in payload["text"]

    # CI gate + --apply refusal in dir mode
    gated = runner.invoke(cli, ["skew-splitkey", str(d), "--ds", "sqlite",
                                "--fail"])
    assert gated.exit_code == 1
    assert "巡检未通过" in gated.output
    refused = runner.invoke(cli, ["skew-splitkey", str(d), "--ds", "sqlite",
                                  "--apply"])
    assert refused.exit_code != 0
    assert "仅支持单个配置文件" in refused.output

    # empty dir → clear error
    empty = tmp_path / "empty"
    empty.mkdir()
    res2 = runner.invoke(cli, ["skew-splitkey", str(empty), "--ds", "sqlite"])
    assert res2.exit_code != 0
    assert "未找到" in res2.output


def test_history_metrics_trend_and_tables(tmp_path):
    from seatunnel_agent.agents.data.data_skew.history import SkewHistory

    h = SkewHistory(tmp_path)
    h.log_splitkey("shop.orders", "region", "good",
                   top1_pct=8.0, ndv=200, null_pct=0.0)
    h.log_splitkey("shop.orders", "region", "good",
                   top1_pct=25.0, ndv=190, null_pct=0.1)
    h.log_splitkey("shop.users", "uid", "good", top1_pct=1.0)

    rec = h.recent(1)[0]
    assert rec["splitkey"]["top1_pct"] == 1.0
    trend = h.splitkey_trend("shop.orders")
    assert [r["splitkey"]["top1_pct"] for r in trend] == [8.0, 25.0]  # oldest first
    assert h.splitkey_tables() == ["shop.users", "shop.orders"]


def test_recheck_drift_line():
    prev = {"timestamp": "2026-09-30T08:00:00+00:00",
            "splitkey": {"table": "orders", "partition_column": "id",
                         "key_verdict": "good", "top1_pct": 8.0}}
    # both verdicts fine but top1 jumped 8% → 25%: drift warning
    line = _recheck_line(prev, "good", "zh", cur_top1=25.0)
    assert "漂移" in line and "8.0%" in line and "25.0%" in line
    assert "+17.0" in line
    # small move stays quiet
    assert _recheck_line(prev, "good", "zh", cur_top1=12.0) == ""
    # no stored metric → quiet (backward compatible with old records)
    old = {"timestamp": "t", "splitkey": {"key_verdict": "good"}}
    assert _recheck_line(old, "good", "zh", cur_top1=90.0) == ""
    en = _recheck_line(prev, "good", "en", cur_top1=25.0)
    assert "drifted" in en


# ---------------------------------------------------------------------------
# sink-side key check
# ---------------------------------------------------------------------------

from seatunnel_agent.agents.data.data_skew.splitkey import (
    parse_seatunnel_sinks,
    render_sinkkey_section,
    run_sink_keys,
    sink_verdict,
)

_CONF_SINK = """
env { parallelism = 2 }
source { Jdbc { table_name = "orders", partition_column = "id" } }
sink {
  Clickhouse { table = "dw.orders", sharding_key = "region" }
  Doris { table.identifier = "dw.orders_d", fenodes = "x:8030" }
}
"""


def test_parse_seatunnel_sinks_block_and_list():
    sinks = parse_seatunnel_sinks(_CONF_SINK)
    # Doris carries no key option in the config → only ClickHouse yields
    assert len(sinks) == 1
    s = sinks[0]
    assert s.plugin == "Clickhouse" and s.option == "sharding_key"
    assert s.columns == ["region"] and s.table == "dw.orders"

    conf_list = """
    source = [{ plugin_name = "Jdbc", table_name = "orders" }]
    sink = [
      { plugin_name = "HdfsFile", partition_by = ["dt", "region"] },
      { plugin_name = "Jdbc", table = "t2", primary_keys = "id, region" }
    ]
    """
    sinks = parse_seatunnel_sinks(conf_list)
    assert [(s.plugin, s.option, s.columns) for s in sinks] == [
        ("HdfsFile", "partition_by", ["dt", "region"]),
        ("Jdbc", "primary_keys", ["id", "region"]),
    ]
    # no sink block at all → []
    assert parse_seatunnel_sinks('source { Jdbc { table_name = "t" } }') == []


def test_sink_verdict_ignores_low_ndv():
    # a 2-value date-ish column is fine as a sink partition key…
    even = SplitStat("dt", total=100, ndv=2, top1_count=15)
    assert sink_verdict(even) == "suspect"  # 15% top1 → mildly hot
    balanced = SplitStat("dt", total=100, ndv=30, top1_count=4)
    assert sink_verdict(balanced) == "good"
    # …but a hot or NULL-heavy one is not
    hot = SplitStat("region", total=100, ndv=2, top1_count=80)
    assert sink_verdict(hot) == "bad"
    nully = SplitStat("k", total=100, ndv=50, null_count=30)
    assert sink_verdict(nully) == "null"


def test_run_sink_keys_and_render(tmp_path):
    from seatunnel_agent.agents.data.text2sql.executor.base import (
        DatabaseConfig,
        create_executor,
    )

    db = _make_orders_db(tmp_path)
    ex = create_executor(
        DatabaseConfig(ds_type="sqlite", host="", port=0, database=str(db)))
    results, src_table = run_sink_keys(ex, _CONF_SINK, ds_type="sqlite")
    assert src_table == "orders"
    assert len(results) == 1
    spec, stats = results[0]
    assert sink_verdict(stats[0]) == "bad"  # region is 80% CN

    md = render_sinkkey_section(results, src_table, "zh")
    assert md.startswith("### Sink 端键体检")
    assert "`region`" in md and "热点键" in md
    assert "物化到目标端存储" in md  # hot note present
    en = render_sinkkey_section(results, src_table, "en")
    assert "### Sink-Side Key Check" in en and "hot key" in en
    # empty results render nothing
    assert render_sinkkey_section([], "orders", "zh") == ""


def test_cli_skew_stats_splitkey_trend(monkeypatch, tmp_path):
    from click.testing import CliRunner

    from seatunnel_agent.agents.data.data_skew.history import default_history
    from seatunnel_agent.cli import cli

    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    h = default_history()
    h.log_splitkey("shop.orders", "region", "bad", top1_pct=80.0)
    h.log_splitkey("shop.orders", "id", "good", top1_pct=2.0)

    runner = CliRunner()
    res = runner.invoke(cli, ["skew-stats"])
    assert res.exit_code == 0, res.output
    assert "分片键巡检" in res.output
    assert "shop.orders" in res.output
    assert "80%" in res.output and "2%" in res.output


# ---------------------------------------------------------------------------
# Drift detection (drift.py)
# ---------------------------------------------------------------------------

def _drift_recs(table, metrics_seq):
    """Build splitkey trend records (oldest first) via a real SkewHistory."""
    import tempfile

    from seatunnel_agent.agents.data.data_skew.history import SkewHistory
    h = SkewHistory(log_dir=tempfile.mkdtemp())
    for m in metrics_seq:
        h.log_splitkey(table, m.get("col", "id"), m.get("verdict", "good"),
                       top1_pct=m.get("top1_pct"), ndv=m.get("ndv"),
                       null_pct=m.get("null_pct"))
    return h.splitkey_trend(table, n=50)


def test_drift_insufficient_history():
    from seatunnel_agent.agents.data.data_skew.drift import compute_drift

    recs = _drift_recs("orders", [{"top1_pct": 10.0}, {"top1_pct": 30.0}])
    r = compute_drift("orders", recs)
    assert r.verdict == "insufficient"
    assert r.samples == 2
    assert r.drifts == []


def test_drift_unmeasured_records_dont_count():
    from seatunnel_agent.agents.data.data_skew.drift import compute_drift

    # 3 records but only 2 carry metrics -> still insufficient
    recs = _drift_recs("orders", [
        {"top1_pct": 10.0}, {}, {"top1_pct": 30.0},
    ])
    r = compute_drift("orders", recs)
    assert r.verdict == "insufficient"
    assert r.samples == 2


def test_drift_stable():
    from seatunnel_agent.agents.data.data_skew.drift import compute_drift

    recs = _drift_recs("orders", [
        {"top1_pct": 11.0, "ndv": 1000, "null_pct": 1.0},
        {"top1_pct": 12.0, "ndv": 980, "null_pct": 1.2},
        {"top1_pct": 13.0, "ndv": 1010, "null_pct": 1.1},
    ])
    r = compute_drift("orders", recs)
    assert r.verdict == "stable"
    assert r.drifts == []
    assert r.column == "id"
    assert r.samples == 3


def test_drift_top1_rise():
    from seatunnel_agent.agents.data.data_skew.drift import compute_drift

    recs = _drift_recs("orders", [
        {"top1_pct": 10.0}, {"top1_pct": 14.0}, {"top1_pct": 28.0},
    ])
    r = compute_drift("orders", recs)
    assert r.verdict == "drift"
    [d] = r.drifts
    assert d.metric == "top1_pct"
    assert d.baseline == 12.0          # median of 10, 14
    assert d.current == 28.0
    assert d.delta == 16.0


def test_drift_null_rise_and_ndv_drop():
    from seatunnel_agent.agents.data.data_skew.drift import compute_drift

    recs = _drift_recs("orders", [
        {"null_pct": 1.0, "ndv": 1000},
        {"null_pct": 2.0, "ndv": 1000},
        {"null_pct": 9.0, "ndv": 600},
    ])
    r = compute_drift("orders", recs)
    assert r.verdict == "drift"
    metrics = {d.metric: d for d in r.drifts}
    assert metrics["null_pct"].delta == 7.5     # 9.0 - median(1,2)=1.5
    assert metrics["ndv"].baseline == 1000
    assert metrics["ndv"].delta == -40.0        # 1000 -> 600 = -40 %


def test_drift_ndv_drop_below_threshold_is_stable():
    from seatunnel_agent.agents.data.data_skew.drift import compute_drift

    recs = _drift_recs("orders", [
        {"ndv": 1000}, {"ndv": 1000}, {"ndv": 800},   # -20 % < 30 %
    ])
    r = compute_drift("orders", recs)
    assert r.verdict == "stable"


def test_drift_series_is_per_column():
    """A table measured under two keys: each column gets its own series —
    the other key's records never pollute the baseline."""
    from seatunnel_agent.agents.data.data_skew.drift import compute_drift

    recs = _drift_recs("orders", [
        {"col": "region", "top1_pct": 20.0},
        {"col": "region", "top1_pct": 25.0},
        {"col": "id", "top1_pct": 1.0},
        {"col": "region", "top1_pct": 80.0},
        {"col": "id", "top1_pct": 1.2},
    ])
    r = compute_drift("orders", recs, column="region")
    assert r.verdict == "drift" and r.column == "region"
    assert r.drifts[0].baseline == 22.5 and r.drifts[0].current == 80.0
    # default column = latest measured record's key (id) → only 2 samples
    r2 = compute_drift("orders", recs)
    assert r2.column == "id" and r2.verdict == "insufficient"


def _seed_drift_history(tmp_path, monkeypatch, metrics_seq, table="orders"):
    from seatunnel_agent.agents.data.data_skew.history import default_history
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    h = default_history()
    for m in metrics_seq:
        h.log_splitkey(table, m.get("col", "id"), m.get("verdict", "good"),
                       top1_pct=m.get("top1_pct"), ndv=m.get("ndv"),
                       null_pct=m.get("null_pct"))
    return h


def test_cli_skew_drift_single_table(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    _seed_drift_history(tmp_path, monkeypatch, [
        {"top1_pct": 10.0}, {"top1_pct": 14.0}, {"top1_pct": 28.0},
    ])
    res = CliRunner().invoke(cli, ["skew-drift", "orders", "--lang", "en"])
    assert res.exit_code == 0, res.output
    assert "Skew drift" in res.output and "orders" in res.output
    assert "top1_pct" in res.output
    assert "12.0" in res.output and "28.0" in res.output and "+16" in res.output
    # the drift patrol itself landed in history (mode='drift')
    from seatunnel_agent.agents.data.data_skew.history import default_history
    rec = default_history().recent(1)[0]
    assert rec["mode"] == "drift"
    assert rec["drift"]["drift_verdict"] == "drift"
    assert rec["drift"]["metrics"] == ["top1_pct"]


def test_cli_skew_drift_sweep_and_insufficient(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    h = _seed_drift_history(tmp_path, monkeypatch, [
        {"top1_pct": 10.0}, {"top1_pct": 11.0}, {"top1_pct": 12.0},
    ])
    h.log_splitkey("t2", "id", "good", top1_pct=5.0)
    res = CliRunner().invoke(cli, ["skew-drift", "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "orders" in res.output and "t2" in res.output
    assert "稳定" in res.output          # orders: stable
    assert "暂无基线" in res.output       # t2: insufficient


def test_cli_skew_drift_empty_history(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    res = CliRunner().invoke(cli, ["skew-drift"])
    assert res.exit_code == 0, res.output
    assert "skew-splitkey" in res.output


def test_cli_skew_drift_webhook(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from seatunnel_agent.agents.data.data_skew import notify
    from seatunnel_agent.cli import cli

    _seed_drift_history(tmp_path, monkeypatch, [
        {"null_pct": 1.0}, {"null_pct": 2.0}, {"null_pct": 9.0},
    ])
    posted = {}

    def fake_post(url, payload):
        posted["url"] = url
        posted["payload"] = payload
        return True, "200"

    monkeypatch.setattr(notify, "post_webhook", fake_post)
    res = CliRunner().invoke(
        cli, ["skew-drift", "--webhook", "http://hook.example/x"])
    assert res.exit_code == 0, res.output
    assert posted["url"] == "http://hook.example/x"
    assert posted["payload"]["kind"] == "skew_drift"
    assert posted["payload"]["tables"] == ["orders"]
    assert "null_pct" in posted["payload"]["text"]


def test_cli_skew_drift_fail_gate(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    _seed_drift_history(tmp_path, monkeypatch, [
        {"top1_pct": 10.0}, {"top1_pct": 14.0}, {"top1_pct": 28.0},
    ])
    runner = CliRunner()
    gated = runner.invoke(cli, ["skew-drift", "orders", "--fail"])
    assert gated.exit_code == 1
    assert "巡检未通过" in gated.output
    # without --fail the same drift stays advisory
    assert runner.invoke(cli, ["skew-drift", "orders"]).exit_code == 0


def test_cli_skew_drift_fail_gate_stable(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    _seed_drift_history(tmp_path, monkeypatch, [
        {"top1_pct": 10.0}, {"top1_pct": 11.0}, {"top1_pct": 12.0},
    ])
    res = CliRunner().invoke(cli, ["skew-drift", "orders", "--fail"])
    assert res.exit_code == 0, res.output


def test_drift_notify_decision():
    from seatunnel_agent.agents.data.data_skew.drift import (
        DriftResult,
        MetricDrift,
        notify_decision,
    )

    drift = DriftResult(table="orders", column="id", verdict="drift",
                        samples=3,
                        drifts=[MetricDrift("top1_pct", 12.0, 28.0, 16.0)])
    prev_same = {"drift": {"table": "orders", "drift_verdict": "drift",
                           "deltas": {"top1_pct": 16.0}}}
    prev_small = {"drift": {"table": "orders", "drift_verdict": "drift",
                            "deltas": {"top1_pct": 11.0}}}
    stable = DriftResult(table="orders", column="id", verdict="stable",
                         samples=4)

    assert notify_decision(None, drift) == (True, "drift")         # first
    assert notify_decision(prev_same, drift) == (False, "")        # duplicate
    assert notify_decision(prev_small, drift) == (True, "worse")   # escalation
    # a new drifted metric escalates even when the old one is unchanged
    drift2 = DriftResult(table="orders", column="id", verdict="drift",
                         samples=4,
                         drifts=[MetricDrift("top1_pct", 12.0, 28.0, 16.0),
                                 MetricDrift("null_pct", 1.0, 7.0, 6.0)])
    assert notify_decision(prev_same, drift2) == (True, "worse")
    assert notify_decision(prev_same, stable) == (True, "recovered")
    assert notify_decision(None, stable) == (False, "")
    insuff = DriftResult(table="orders", verdict="insufficient", samples=1)
    assert notify_decision(prev_same, insuff) == (False, "")


def test_cli_skew_drift_webhook_suppression(tmp_path, monkeypatch):
    """Unchanged drift alerts once; escalation re-alerts; --webhook-all
    bypasses; recovery posts a recovery card."""
    from click.testing import CliRunner

    from seatunnel_agent.agents.data.data_skew import notify
    from seatunnel_agent.cli import cli

    h = _seed_drift_history(tmp_path, monkeypatch, [
        {"top1_pct": 10.0}, {"top1_pct": 14.0}, {"top1_pct": 28.0},
    ])
    posted: list[dict] = []
    monkeypatch.setattr(notify, "post_webhook",
                        lambda url, payload: (posted.append(payload)
                                              or (True, "200")))
    runner = CliRunner()
    args = ["skew-drift", "orders", "--webhook", "http://hook/x"]
    runner.invoke(cli, args)
    assert len(posted) == 1                     # first report
    runner.invoke(cli, args)
    assert len(posted) == 1                     # unchanged → suppressed
    runner.invoke(cli, args + ["--webhook-all"])
    assert len(posted) == 2                     # escape hatch
    h.log_splitkey("orders", "id", "good", top1_pct=55.0)   # drift worsens
    runner.invoke(cli, args)
    assert len(posted) == 3                     # escalation re-alerts
    # recovery: pre-logged drift + stable series → one recovery card
    h2 = _seed_drift_history(tmp_path, monkeypatch, [
        {"top1_pct": 10.0}, {"top1_pct": 11.0}, {"top1_pct": 12.0},
    ], table="t_rec")
    h2.log_drift("t_rec", "drift", ["top1_pct"],
                 deltas={"top1_pct": 15.0})
    res = runner.invoke(cli, ["skew-drift", "t_rec",
                              "--webhook", "http://hook/x"])
    assert res.exit_code == 0, res.output
    assert len(posted) == 4
    assert posted[-1]["recovered"] == ["t_rec"]
    assert "恢复" in posted[-1]["text"]


def test_render_drift_i18n_parity():
    from seatunnel_agent.agents.data.data_skew.drift import (
        DriftResult,
        MetricDrift,
        render_drift,
    )
    from seatunnel_agent.agents.data.data_skew.i18n import DSK_I18N

    r = DriftResult(table="orders", column="id", verdict="drift", samples=4,
                    drifts=[MetricDrift("top1_pct", 12.0, 28.0, 16.0)])
    zh, en = render_drift(r, "zh"), render_drift(r, "en")
    assert "漂移" in zh and "drifted" in en
    for key in ("drf_drift", "drf_metric", "drf_stable",
                "drf_insufficient", "drf_none"):
        assert key in DSK_I18N["en"] and key in DSK_I18N["zh"]


def test_api_skew_drift(tmp_path, monkeypatch):
    client = _api_client(tmp_path, monkeypatch)
    from seatunnel_agent.agents.data.data_skew.history import default_history

    h = default_history()
    for top1 in (10.0, 14.0, 28.0):
        h.log_splitkey("orders", "id", "good", top1_pct=top1)
    h.log_splitkey("t2", "id", "good", top1_pct=5.0)

    # one table, drifted
    resp = client.get("/api/skew/drift", params={"table": "orders", "lang": "en"})
    assert resp.status_code == 200
    [item] = resp.json()["items"]
    assert item["verdict"] == "drift"
    assert item["column"] == "id"
    assert item["samples"] == 3
    [d] = item["drifts"]
    assert d == {"metric": "top1_pct", "baseline": 12.0,
                 "current": 28.0, "delta": 16.0}
    assert "drifted" in item["text"]

    # sweep: both tables, t2 insufficient
    resp = client.get("/api/skew/drift", params={"lang": "zh"})
    items = {i["table"]: i for i in resp.json()["items"]}
    assert items["orders"]["verdict"] == "drift"
    assert items["t2"]["verdict"] == "insufficient"
    assert "暂无基线" in items["t2"]["text"]

    # empty history
    resp = client.get("/api/skew/drift", params={"table": "nope"})
    [item] = resp.json()["items"]
    assert item["verdict"] == "insufficient"
    assert item["samples"] == 0
