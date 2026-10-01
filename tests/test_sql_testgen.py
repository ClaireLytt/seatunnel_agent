# -*- coding: utf-8 -*-
"""Tests for the SQL test-data generator (sql_testgen).

Deterministic only — no LLM, no external database (SQLite is stdlib).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.sql_testgen import (
    generate,
    render_markdown,
    result_to_dict,
    validate_with_sqlite,
    write_outputs,
)

runner = CliRunner()

DEMO = Path(__file__).resolve().parents[1] / "examples" / "testgen_demo"

JOIN_SQL = """
SELECT u.user_id, u.user_name, sum(o.amount) AS pay_amount
FROM dwd.user_info u
JOIN dwd.order_pay o ON u.user_id = o.user_id
WHERE o.dt = '2024-01-01' AND o.status IN ('PAID', 'DONE')
GROUP BY u.user_id, u.user_name
"""

DDL = """
CREATE TABLE dwd.user_info (
  user_id BIGINT COMMENT '用户ID',
  user_name STRING COMMENT '姓名'
) PARTITIONED BY (dt STRING);
"""


def _table(result, name):
    return next(t for t in result.tables if t.name == name)


def _col_idx(table, name):
    return next(i for i, c in enumerate(table.columns) if c.name == name)


# ─────────────────────────── generation ───────────────────────────

def test_generate_finds_both_tables():
    result = generate(JOIN_SQL)
    assert {t.name for t in result.tables} == {"dwd.user_info",
                                               "dwd.order_pay"}
    assert all(len(t.rows) == 5 for t in result.tables)


def test_join_columns_share_value_pool():
    result = generate(JOIN_SQL)
    users = _table(result, "dwd.user_info")
    orders = _table(result, "dwd.order_pay")
    u_ids = {r[_col_idx(users, "user_id")] for r in users.rows}
    o_ids = {r[_col_idx(orders, "user_id")] for r in orders.rows}
    assert u_ids == o_ids and len(u_ids) == 5


def test_where_literals_are_satisfied():
    result = generate(JOIN_SQL)
    orders = _table(result, "dwd.order_pay")
    dts = [r[_col_idx(orders, "dt")] for r in orders.rows]
    stats = [r[_col_idx(orders, "status")] for r in orders.rows]
    assert dts.count("2024-01-01") >= 3     # most rows satisfy the filter
    assert "PAID" in stats
    # the last row deliberately misses the filter
    assert dts[-1] != "2024-01-01"


def test_boundary_rows_null_and_zero():
    result = generate(JOIN_SQL)
    orders = _table(result, "dwd.order_pay")
    amounts = [r[_col_idx(orders, "amount")] for r in orders.rows]
    assert None in amounts
    assert 0.0 in amounts


def test_ddl_types_take_precedence():
    result = generate(JOIN_SQL, ddl=DDL)
    users = _table(result, "dwd.user_info")
    by_name = {c.name: c for c in users.columns}
    assert by_name["user_id"].source == "ddl"
    assert by_name["user_id"].col_type == "BIGINT"
    assert by_name["dt"].source == "ddl"    # DDL adds unreferenced columns


def test_inferred_types_by_name_and_literal():
    result = generate("SELECT order_cnt, gmv_amount, remark FROM t "
                      "WHERE uid = 42")
    (table,) = result.tables
    types = {c.name: c.col_type for c in table.columns}
    assert types["order_cnt"] == "BIGINT"
    assert types["gmv_amount"] == "DOUBLE"
    assert types["remark"] == "STRING"
    assert types["uid"] == "BIGINT"          # from the integer literal


def test_cte_is_not_a_physical_table():
    result = generate(
        "WITH base AS (SELECT user_id FROM ods.u) "
        "SELECT * FROM base JOIN ods.v ON base.user_id = v.user_id")
    names = {t.name for t in result.tables}
    assert "base" not in names
    assert {"ods.u", "ods.v"} <= names


def test_insert_select_targets_sources_only():
    result = generate(
        "INSERT OVERWRITE TABLE ads.report "
        "SELECT user_id FROM dwd.user_info WHERE dt = '2024-01-01'")
    assert {t.name for t in result.tables} == {"dwd.user_info"}
    assert any("INSERT" in n for n in result.notes)


def test_with_insert_keeps_cte_transparent():
    # Hive WITH ... INSERT hangs the CTEs on the Insert node; the unwrap must
    # carry them over or 'base' reads as a physical table
    result = generate(
        "WITH base AS (SELECT user_id FROM ods.u) "
        "INSERT INTO ads.t SELECT user_id FROM base")
    assert {t.name for t in result.tables} == {"ods.u"}
    v = validate_with_sqlite(result)
    assert v.status == "ok" and v.row_count > 0


def test_join_key_with_literal_satisfies_both():
    # a column that is both a join key and literal-constrained must carry the
    # literal on BOTH sides, or the query returns 0 rows
    result = generate(
        "SELECT a.id, b.v FROM t1 a JOIN t2 b ON a.id = b.id WHERE a.id = 5")
    for name in ("t1", "t2"):
        table = _table(result, name)
        ids = [r[_col_idx(table, "id")] for r in table.rows]
        assert ids.count(5) >= 3, (name, ids)
    v = validate_with_sqlite(result)
    assert v.status == "ok" and v.row_count > 0


def test_reversed_literal_is_recorded():
    result = generate("SELECT a FROM t WHERE 5 = t.a")
    (table,) = result.tables
    a_vals = [r[_col_idx(table, "a")] for r in table.rows]
    assert 5 in a_vals
    v = validate_with_sqlite(result)
    assert v.status == "ok" and v.row_count > 0


def test_parse_error_is_warning():
    result = generate("SELECT FROM WHERE")
    assert not result.tables
    assert result.warnings


def test_rows_clamped():
    result = generate("SELECT a FROM t", rows=1000)
    assert len(result.tables[0].rows) == 100


# ─────────────────────────── sqlite validation ───────────────────────────

def test_validate_join_query_returns_rows():
    result = generate(JOIN_SQL, ddl=DDL)
    v = validate_with_sqlite(result)
    assert v.status == "ok", v.detail
    assert v.row_count > 0


def test_validate_simple_filter():
    result = generate("SELECT a, b FROM t WHERE a = 'x'")
    v = validate_with_sqlite(result)
    assert v.status == "ok"
    assert v.row_count >= 1


def test_validate_unsupported_function_is_inconclusive():
    result = generate("SELECT get_json_object(payload, '$.a') FROM t")
    v = validate_with_sqlite(result)
    # either sqlglot cannot translate it, or sqlite lacks the function —
    # both are reported as inconclusive, never a crash
    assert v.status in ("transpile_error", "exec_error")


def test_validate_no_tables_skipped():
    result = generate("SELECT FROM WHERE")
    v = validate_with_sqlite(result)
    assert v.status == "skipped"


# ─────────────────────────── outputs ───────────────────────────

def test_csv_and_insert_sql_shapes():
    result = generate(JOIN_SQL, ddl=DDL)
    users = _table(result, "dwd.user_info")
    csv_text = users.csv_text()
    assert csv_text.splitlines()[0].startswith("user_id,")
    assert len(csv_text.splitlines()) == 6     # header + 5 rows
    assert "INSERT INTO dwd.user_info" in users.insert_sql()
    assert "NULL" in users.insert_sql()
    assert "CREATE TABLE dwd.user_info" in users.create_sql()


def test_write_outputs(tmp_path):
    result = generate(JOIN_SQL)
    written = write_outputs(result, tmp_path / "out")
    names = {p.name for p in written}
    assert "dwd__user_info.csv" in names
    assert "create_tables.sql" in names and "inserts.sql" in names
    csv_file = next(p for p in written if p.name.endswith("user_info.csv"))
    assert csv_file.read_text(encoding="utf-8-sig").startswith("user_id")


def test_render_markdown_zh_and_en():
    result = generate(JOIN_SQL, ddl=DDL)
    result.validation = validate_with_sqlite(result)
    zh = render_markdown(result, "zh")
    en = render_markdown(result, "en")
    assert "SQL 测试数据生成" in zh and "SQLite 验证" in zh
    assert "SQL Test Data Generator" in en and "SQLite validation" in en


def test_result_to_dict_is_json_serializable():
    result = generate(JOIN_SQL)
    result.validation = validate_with_sqlite(result)
    json.dumps(result_to_dict(result))


# ─────────────────────────── CLI ───────────────────────────

def test_cli_testgen_inline():
    r = runner.invoke(cli, ["testgen", "--sql",
                            "SELECT a FROM t WHERE dt = '2024-01-01'"])
    assert r.exit_code == 0, r.output
    assert "SQL 测试数据生成" in r.output


def test_cli_testgen_requires_source():
    r = runner.invoke(cli, ["testgen"])
    assert r.exit_code != 0


def test_cli_testgen_demo_files_with_out(tmp_path):
    out_dir = tmp_path / "data"
    r = runner.invoke(cli, [
        "testgen", "--file", str(DEMO / "query.sql"),
        "--ddl", str(DEMO / "ddl.sql"), "--out", str(out_dir),
        "--fail-on", "error"])
    assert r.exit_code == 0, r.output
    assert (out_dir / "create_tables.sql").is_file()
    assert (out_dir / "dwd__order_pay.csv").is_file()


def test_cli_testgen_json():
    r = runner.invoke(cli, ["testgen", "--sql", "SELECT a FROM t",
                            "-F", "json", "--no-validate"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data["tables"][0]["name"] == "t"
    assert data["validation"] is None


def test_cli_testgen_fail_on_error():
    r = runner.invoke(cli, ["testgen", "--sql", "SELECT FROM WHERE",
                            "--fail-on", "error"])
    assert r.exit_code == 1


# ─────────────────────────── REST API ───────────────────────────

@pytest.fixture()
def api_client():
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.sql_testgen.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_generate(api_client):
    r = api_client.post("/api/testgen/generate", json={
        "sql": JOIN_SQL, "ddl": DDL, "lang": "en", "report": True})
    assert r.status_code == 200
    data = r.json()
    assert len(data["result"]["tables"]) == 2
    assert data["result"]["validation"]["status"] == "ok"
    assert "SQL Test Data Generator" in data["report"]


def test_api_generate_no_validate(api_client):
    r = api_client.post("/api/testgen/generate", json={
        "sql": "SELECT a FROM t", "validate_sqlite": False})
    assert r.status_code == 200
    assert r.json()["result"]["validation"] is None


def test_api_generate_bad_sql(api_client):
    r = api_client.post("/api/testgen/generate", json={
        "sql": "SELECT FROM WHERE"})
    assert r.status_code == 400
    assert api_client.get("/api/testgen/health").json()["status"] == "ok"
