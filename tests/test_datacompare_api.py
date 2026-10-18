"""In-process tests for the Data Comparison REST API (ticket 02).

Seam: the HTTP contract of /api/datacompare (session create, meta,
per-side connect, tables listing) — never the internals of the
registry or the executors. Real connections are exercised against
file-backed SQLite fixtures.
"""

from __future__ import annotations

import json
import sqlite3
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    from seatunnel_agent.agents.data.data_comparison.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _make_db(path, tables: dict[str, list[tuple]]) -> str:
    conn = sqlite3.connect(path)
    for name, rows in tables.items():
        conn.execute(f"CREATE TABLE {name} (id INTEGER, val TEXT)")
        conn.executemany(f"INSERT INTO {name} VALUES (?, ?)", rows)
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture()
def db_a(tmp_path):
    return _make_db(tmp_path / "a.db",
                    {"orders": [(1, "x"), (2, "y")], "users": [(1, "u")]})


@pytest.fixture()
def db_b(tmp_path):
    return _make_db(tmp_path / "b.db", {"orders": [(1, "x")]})


def _session(client: TestClient) -> str:
    r = client.post("/api/datacompare/session")
    assert r.status_code == 200
    sid = r.json()["session_id"]
    assert isinstance(sid, str) and sid
    return sid


def _connect(client, sid, side, **kw):
    body = {"session_id": sid, "side": side, "ds_type": "sqlite",
            "host": "", "port": "", "db": "", "username": "",
            "password": "", "lang": "en"}
    body.update(kw)
    return client.post("/api/datacompare/connect", json=body)


# ── meta ────────────────────────────────────────────────────────────


def test_meta_lists_datasources(client):
    r = client.get("/api/datacompare/meta")
    assert r.status_code == 200
    data = r.json()
    by_key = {d["key"]: d for d in data["datasources"]}
    assert by_key["sqlite"]["label"] == "SQLite"
    assert by_key["sqlite"]["needs_host"] is False
    assert by_key["sqlite"]["needs_auth"] is False
    assert by_key["mysql"]["needs_host"] is True
    assert by_key["mysql"]["needs_auth"] is True
    assert by_key["mysql"]["default_port"] == 3306
    assert by_key["hive"]["needs_auth"] is False
    assert by_key["hive"]["default_db"] == "default"
    assert data["sample_strategies"] == ["TOP N", "RANDOM", "STRATIFIED"]
    assert "15" in data["schedule_intervals"]


# ── session ─────────────────────────────────────────────────────────


def test_session_create_issues_unique_ids(client):
    assert _session(client) != _session(client)


# ── connect ─────────────────────────────────────────────────────────


def test_connect_sqlite_success_per_side(client, db_a, db_b):
    sid = _session(client)

    ra = _connect(client, sid, "a", db=db_a).json()
    assert ra["ok"] is True
    assert ra["tables"] == ["orders", "users"]
    assert ra["status"].startswith("✅ SQLite")
    assert "2 tables loaded" in ra["status"]
    assert ra["resolved"]["database"] == db_a

    rb = _connect(client, sid, "b", db=db_b).json()
    assert rb["ok"] is True
    assert rb["tables"] == ["orders"]

    # side A untouched by side B's connect
    ta = client.get("/api/datacompare/tables",
                    params={"session_id": sid, "side": "a"}).json()
    assert ta["tables"] == ["orders", "users"]


def test_connect_failure_missing_host(client, monkeypatch):
    monkeypatch.delenv("MYSQL_HOST", raising=False)
    sid = _session(client)
    r = _connect(client, sid, "a", ds_type="mysql")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    assert "MYSQL_HOST" in data["error"]


def test_connect_failure_bad_port(client):
    sid = _session(client)
    data = _connect(client, sid, "a", ds_type="mysql",
                    host="example.invalid", port="not-a-number").json()
    assert data["ok"] is False
    assert "Port" in data["error"] or "端口" in data["error"]


def test_connect_unknown_session_404(client, db_a):
    r = _connect(client, "deadbeef", "a", db=db_a)
    assert r.status_code == 404


def test_connect_invalid_side_422(client, db_a):
    sid = _session(client)
    r = _connect(client, sid, "c", db=db_a)
    assert r.status_code == 422


def test_connect_unknown_ds_type(client):
    sid = _session(client)
    data = _connect(client, sid, "a", ds_type="nosuchdb").json()
    assert data["ok"] is False


# ── tables ──────────────────────────────────────────────────────────


def test_tables_before_connect_empty(client):
    sid = _session(client)
    r = client.get("/api/datacompare/tables",
                   params={"session_id": sid, "side": "b"})
    assert r.status_code == 200
    assert r.json()["tables"] == []


def test_tables_unknown_session_404(client):
    r = client.get("/api/datacompare/tables",
                   params={"session_id": "nope", "side": "a"})
    assert r.status_code == 404


# ── presets (ticket 05) ─────────────────────────────────────────────


@pytest.fixture()
def presets_tmp(tmp_path, monkeypatch):
    """Point the API's presets store (and its key file) at tmp_path."""
    from seatunnel_agent.agents.data.data_comparison import api as api_mod
    from seatunnel_agent.agents.data.data_comparison import presets as presets_mod
    from seatunnel_agent.agents.data.data_comparison.presets import (
        ConnectionPresetsStore,
    )

    monkeypatch.setattr(presets_mod, "_KEY_PATH", tmp_path / "dc_secret.key")
    monkeypatch.setattr(presets_mod, "_cached_key", None)
    store = ConnectionPresetsStore(tmp_path / "dc_connections.json")
    monkeypatch.setattr(api_mod, "_PRESETS_STORE", store)
    return store


def _save_preset(client, **kw):
    body = {"name": "prod-mysql", "ds_type": "mysql", "host": "db.example",
            "port": 3306, "database": "sales", "username": "u",
            "password": "s3cret", "environment": "prod"}
    body.update(kw)
    return client.post("/api/datacompare/presets", json=body)


def test_presets_list_empty(client, presets_tmp):
    r = client.get("/api/datacompare/presets")
    assert r.status_code == 200
    assert r.json()["presets"] == []


def test_presets_save_load_delete_round_trip(client, presets_tmp):
    r = _save_preset(client)
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # list shows summary fields only — never the password
    listed = client.get("/api/datacompare/presets").json()["presets"]
    assert [(p["name"], p["environment"]) for p in listed] == [
        ("prod-mysql", "prod")]
    assert "password" not in listed[0]

    # load returns the full connection (password decrypted to fill the form)
    full = client.get("/api/datacompare/presets/prod-mysql").json()
    assert full["ds_type"] == "mysql"
    assert full["host"] == "db.example"
    assert full["port"] == 3306
    assert full["database"] == "sales"
    assert full["username"] == "u"
    assert full["password"] == "s3cret"
    assert full["environment"] == "prod"

    r = client.delete("/api/datacompare/presets/prod-mysql")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert client.get("/api/datacompare/presets").json()["presets"] == []


def test_presets_save_same_name_replaces(client, presets_tmp):
    _save_preset(client)
    _save_preset(client, host="other.example", environment="staging")
    listed = client.get("/api/datacompare/presets").json()["presets"]
    assert len(listed) == 1
    full = client.get("/api/datacompare/presets/prod-mysql").json()
    assert full["host"] == "other.example"
    assert full["environment"] == "staging"


def test_presets_save_empty_name_rejected(client, presets_tmp):
    r = _save_preset(client, name="   ")
    assert r.status_code == 400


def test_presets_load_unknown_404(client, presets_tmp):
    assert client.get("/api/datacompare/presets/nope").status_code == 404


def test_presets_delete_unknown_404(client, presets_tmp):
    assert client.delete("/api/datacompare/presets/nope").status_code == 404

# ── ticket 03: core comparison actions ──────────────────────────────


@pytest.fixture()
def connected(client, db_a, db_b) -> str:
    """Session with both sides connected to the SQLite fixtures."""
    sid = _session(client)
    assert _connect(client, sid, "a", db=db_a).json()["ok"] is True
    assert _connect(client, sid, "b", db=db_b).json()["ok"] is True
    return sid


def _action(client, sid, action, **kw):
    body = {"session_id": sid, "table_a": "orders", "table_b": "orders",
            "lang": "en"}
    body.update(kw)
    return client.post(f"/api/datacompare/compare/{action}", json=body)


def test_compare_schema_identical_card(client, connected):
    r = _action(client, connected, "schema")
    assert r.status_code == 200
    html = r.json()["html"]
    assert "Schema Comparison" in html
    assert "Schemas are identical" in html


def test_compare_schema_diff_card(client, connected, tmp_path):
    # side B gets a table with an extra column -> "added" row in the card
    db_c = tmp_path / "c.db"
    conn = sqlite3.connect(db_c)
    conn.execute("CREATE TABLE orders (id INTEGER, val TEXT, extra REAL)")
    conn.commit()
    conn.close()
    assert _connect(client, connected, "b", db=str(db_c)).json()["ok"] is True
    html = _action(client, connected, "schema").json()["html"]
    assert "Added" in html
    assert "extra" in html


def test_compare_count_card_with_threshold(client, connected):
    # a.orders=2 rows, b.orders=1 row -> delta -1 (-50%)
    html = _action(client, connected, "count", threshold="10%").json()["html"]
    assert "Row Count Comparison" in html
    assert "<b>2</b>" in html and "<b>1</b>" in html
    assert "Delta: +1 (+50.0%)" in html
    assert "FAIL" in html

    html2 = _action(client, connected, "count", threshold="60%").json()["html"]
    assert "PASS" in html2


def test_compare_count_where_filters_rows(client, connected):
    """Options semantics: WHERE narrows the counted rows on both sides.

    Unfiltered, a.orders=2 vs b.orders=1 fails a 10% threshold; with
    WHERE id = 1 both sides count exactly one row, so the same
    threshold passes — proving the clause reaches the SQL.
    """
    unfiltered = _action(client, connected, "count",
                         threshold="10%").json()["html"]
    assert "FAIL" in unfiltered

    filtered = _action(client, connected, "count", threshold="10%",
                       where="id = 1").json()["html"]
    assert "Count (A): <b>1</b>" in filtered
    assert "Count (B): <b>1</b>" in filtered
    assert "Match" in filtered
    assert "FAIL" not in filtered


def test_compare_sample_keyed_card(client, connected):
    html = _action(client, connected, "sample",
                   key_columns="id").json()["html"]
    assert "Key-Based Diff" in html
    assert "Removed rows" in html and "-1" in html


def test_compare_aggregate_card(client, connected):
    html = _action(client, connected, "aggregate").json()["html"]
    assert "Aggregate Comparison" in html


def test_compare_guard_not_connected(client):
    sid = _session(client)
    html = _action(client, sid, "schema").json()["html"]
    assert html == "Please connect both data sources first"


def test_compare_guard_tables_missing(client, connected):
    html = _action(client, connected, "schema", table_a="").json()["html"]
    assert html == "Please select tables on both sides"


def test_compare_guard_where_ddl(client, connected):
    html = _action(client, connected, "count",
                   where="1=1; DROP TABLE x").json()["html"]
    assert "forbidden keyword" in html


def test_compare_unknown_session_404(client):
    r = _action(client, "nope", "schema")
    assert r.status_code == 404


def test_compare_error_is_card_not_500(client, connected):
    html = _action(client, connected, "count",
                   table_b="no_such_table").json()["html"]
    assert "❌" in html


# ── feature accordions (ticket 06) ──────────────────────────────────


def test_feature_checksum_identical(client, connected, db_a):
    # same database on both sides -> every segment matches
    assert _connect(client, connected, "b", db=db_a).json()["ok"] is True
    html = _action(client, connected, "checksum").json()["html"]
    assert "Checksum Comparison" in html
    assert "All segments match" in html


def test_feature_checksum_mismatch(client, connected):
    # a.orders has 2 rows, b.orders 1 row -> the single sqlite segment differs
    html = _action(client, connected, "checksum",
                   checksum_columns="id, val").json()["html"]
    assert "Checksum Comparison" in html
    assert "Mismatch" in html


def test_feature_chunked_requires_key_columns(client, connected):
    html = _action(client, connected, "chunked").json()["html"]
    assert "Fill Key Columns with a numeric primary key first" in html


def test_feature_chunked_card(client, connected):
    html = _action(client, connected, "chunked",
                   key_columns="id").json()["html"]
    assert "Chunked Verification" in html
    # a has row id=2 that b lacks -> at least one mismatched chunk
    assert "mismatched" in html


def test_feature_chunked_all_match(client, connected, db_a):
    assert _connect(client, connected, "b", db=db_a).json()["ok"] is True
    html = _action(client, connected, "chunked",
                   key_columns="id").json()["html"]
    assert "All chunks match" in html


def test_feature_sql_identical(client, connected):
    html = _action(client, connected, "sql",
                   sql_a="SELECT id FROM orders WHERE id = 1",
                   sql_b="SELECT id FROM orders WHERE id = 1").json()["html"]
    assert "Result sets are identical" in html


def test_feature_sql_diff(client, connected):
    html = _action(client, connected, "sql",
                   sql_a="SELECT id, val FROM orders",
                   sql_b="SELECT id, val FROM orders").json()["html"]
    # a.orders has (2, 'y') which b lacks -> only-in-A row
    assert "only in A" in html


def test_feature_sql_rejects_non_select(client, connected):
    html = _action(client, connected, "sql",
                   sql_a="DELETE FROM orders",
                   sql_b="SELECT 1").json()["html"]
    assert html == "Only SELECT statements are allowed"


def test_feature_sql_rejects_ddl_keyword(client, connected):
    html = _action(client, connected, "sql",
                   sql_a="SELECT 1; DROP TABLE orders",
                   sql_b="SELECT 1").json()["html"]
    assert html == "Only SELECT statements are allowed"


def test_feature_sql_requires_connection(client):
    sid = _session(client)
    html = _action(client, sid, "sql", sql_a="SELECT 1",
                   sql_b="SELECT 1").json()["html"]
    assert html == "Please connect both data sources first"


def test_feature_incremental_requires_watermark(client, connected):
    # legacy returns the watermark hint string as the guard message
    html = _action(client, connected, "incremental").json()["html"]
    assert html == "e.g. updated_at"


def test_feature_incremental_keyed_card(client, connected):
    html = _action(client, connected, "incremental",
                   watermark_col="id", watermark_val="0",
                   key_columns="id").json()["html"]
    assert "Key-Based Diff" in html


def test_feature_quality_requires_rules(client, connected):
    # legacy returns the rules hint string as the guard message
    html = _action(client, connected, "quality").json()["html"]
    assert html == "e.g. name:not_null>95, age:range:0-150"


def test_feature_quality_card_both_sides(client, connected):
    html = _action(client, connected, "quality",
                   quality_rules="id:not_null>95").json()["html"]
    assert html.count("Quality Check Result") == 2
    assert "PASS" in html


def test_feature_skew_requires_columns(client, connected):
    html = _action(client, connected, "skew").json()["html"]
    assert "Please specify columns to analyze" in html


def test_feature_skew_card(client, connected):
    html = _action(client, connected, "skew",
                   skew_columns="val").json()["html"]
    assert "Data Skew Analysis" in html


def test_feature_partition_requires_column(client, connected):
    html = _action(client, connected, "partition").json()["html"]
    assert "Column to partition by" in html


def test_feature_partition_card(client, connected):
    html = _action(client, connected, "partition",
                   partition_col="val").json()["html"]
    assert "Partition Comparison" in html


def test_feature_custom_agg_requires_expressions(client, connected):
    html = _action(client, connected, "custom-agg").json()["html"]
    assert "One per line: alias=EXPRESSION" in html


def test_feature_custom_agg_card(client, connected):
    html = _action(client, connected, "custom-agg",
                   expressions="total=SUM(id)").json()["html"]
    assert "Custom Aggregate Comparison" in html
    # SUM(id): a=3, b=1 -> the alias row surfaces in the card
    assert "total" in html


def test_feature_guard_not_connected(client):
    sid = _session(client)
    for action, extra in [
        ("checksum", {}),
        ("chunked", {"key_columns": "id"}),
        ("partition", {"partition_col": "val"}),
        ("custom-agg", {"expressions": "t=SUM(id)"}),
        ("skew", {"skew_columns": "val"}),
        ("incremental", {"watermark_col": "id"}),
        ("quality", {"quality_rules": "id:not_null>95"}),
    ]:
        html = _action(client, sid, action, **extra).json()["html"]
        assert html == "Please connect both data sources first", action


def test_feature_where_applies_to_checksum(client, connected):
    # WHERE id = 1 leaves identical single rows on both sides
    html = _action(client, connected, "checksum",
                   where="id = 1").json()["html"]
    assert "All segments match" in html


def test_feature_unknown_session_404(client):
    r = _action(client, "nope", "checksum")
    assert r.status_code == 404


# ── ticket 07: report save / list / load / diff / export / standalone ──


@pytest.fixture()
def reports_tmp(tmp_path, monkeypatch):
    """Point the reports API at a temp reports directory."""
    from seatunnel_agent.agents.data.data_comparison import reports_api
    rdir = tmp_path / "reports"
    monkeypatch.setattr(reports_api, "_REPORTS_DIR", rdir)
    return rdir


@pytest.fixture()
def compared(client, connected, reports_tmp) -> str:
    """Connected session with a report populated via count + schema."""
    assert _action(client, connected, "count").status_code == 200
    assert _action(client, connected, "schema").status_code == 200
    return connected


def _save_report(client, sid, **kw):
    body = {"session_id": sid, "table_a": "orders", "table_b": "orders",
            "lang": "en"}
    body.update(kw)
    return client.post("/api/datacompare/reports", json=body)


def test_report_save_list_load_round_trip(client, compared, reports_tmp):
    r = _save_report(client, compared)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    fname = data["filename"]
    assert fname.startswith("compare_orders_vs_orders_")
    assert fname.endswith(".json")
    assert (reports_tmp / fname).is_file()

    files = client.get("/api/datacompare/reports").json()["files"]
    assert files == [fname]

    # load into a FRESH session restores the report view
    sid2 = _session(client)
    r = client.get(f"/api/datacompare/reports/{fname}",
                   params={"session_id": sid2, "lang": "en"})
    assert r.status_code == 200
    html = r.json()["html"]
    assert "Report loaded" in html
    assert "Row Count Comparison" in html
    assert "Schema Comparison" in html

    # ...and the loaded report is now the session's last_report:
    # exports work from the fresh session
    rr = client.get("/api/datacompare/export/csv",
                    params={"session_id": sid2, "lang": "en"})
    assert rr.status_code == 200


def test_report_save_without_report_is_error(client, connected, reports_tmp):
    data = _save_report(client, connected).json()
    assert data["ok"] is False


def test_report_list_empty(client, reports_tmp):
    assert client.get("/api/datacompare/reports").json()["files"] == []


def test_report_load_unknown_404(client, compared):
    r = client.get("/api/datacompare/reports/compare_nope.json",
                   params={"session_id": compared, "lang": "en"})
    assert r.status_code == 404


def test_report_load_rejects_traversal(client, compared):
    r = client.get("/api/datacompare/reports/..%2Fsecrets.json",
                   params={"session_id": compared, "lang": "en"})
    assert r.status_code == 404


def test_report_diff_contract(client, compared):
    f1 = _save_report(client, compared).json()["filename"]
    # change the data so the second report differs
    assert _action(client, compared, "count", table_a="users",
                   table_b="orders").status_code == 200
    f2 = _save_report(client, compared, table_a="users").json()["filename"]
    assert f1 != f2

    r = client.post("/api/datacompare/reports/diff",
                    json={"old": f1, "new": f2, "lang": "en"})
    assert r.status_code == 200
    html = r.json()["html"]
    assert "Report Diff Result" in html
    assert "row_count" in html


def test_report_diff_unknown_404(client, compared, reports_tmp):
    r = client.post("/api/datacompare/reports/diff",
                    json={"old": "compare_a.json", "new": "compare_b.json",
                          "lang": "en"})
    assert r.status_code == 404


def test_export_csv_valid(client, compared):
    r = client.get("/api/datacompare/export/csv",
                   params={"session_id": compared, "lang": "en"})
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    cd = r.headers["content-disposition"]
    assert "data_comparison_" in cd and ".csv" in cd

    import csv
    import io
    text = r.content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    flat = [c for row in rows for c in row]
    assert "[Row Count]" in flat
    assert "[Schema Diff]" in flat


def test_export_excel_valid(client, compared):
    r = client.get("/api/datacompare/export/xlsx",
                   params={"session_id": compared, "lang": "en"})
    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    assert "data_comparison_" in cd and ".xlsx" in cd

    import io

    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(r.content))
    assert "Row Count" in wb.sheetnames
    assert "Schema Diff" in wb.sheetnames
    ws = wb["Row Count"]
    assert ws.cell(row=1, column=1).value == "Table A"
    assert ws.cell(row=2, column=2).value == 2  # count A (orders has 2 rows)


def test_export_without_report_409(client, connected):
    for fmt in ("csv", "xlsx"):
        r = client.get(f"/api/datacompare/export/{fmt}",
                       params={"session_id": connected, "lang": "en"})
        assert r.status_code == 409


def test_export_unknown_session_404(client):
    r = client.get("/api/datacompare/export/csv",
                   params={"session_id": "nope", "lang": "en"})
    assert r.status_code == 404


def test_standalone_report_html(client, compared):
    r = client.get("/api/datacompare/report/standalone",
                   params={"session_id": compared, "lang": "en"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    html = r.text
    assert "<html" in html.lower()
    assert "Row Count Comparison" in html
    assert "Schema Comparison" in html


def test_standalone_without_report_409(client, connected, reports_tmp):
    r = client.get("/api/datacompare/report/standalone",
                   params={"session_id": connected, "lang": "en"})
    assert r.status_code == 409


# ── ticket 04: compound actions with progress ───────────────────────


def _frames(text: str) -> list[dict]:
    """Parse SSE 'data: {json}' frames from a buffered response body."""
    return [json.loads(line[6:]) for line in text.splitlines()
            if line.startswith("data: ")]


def _compound(client, sid, action, **kw):
    body = {"session_id": sid, "table_a": "orders", "table_b": "orders",
            "lang": "en"}
    body.update(kw)
    return client.post(f"/api/datacompare/compare/{action}", json=body)


def test_compare_all_streams_progress_then_done(client, connected):
    r = _compound(client, connected, "all")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    frames = _frames(r.text)
    progress = [f for f in frames if f["event"] == "progress"]
    assert progress, "expected at least one progress frame"
    for f in progress:
        assert 0 < f["value"] <= 1
        assert isinstance(f["desc"], str)
    assert frames[-1]["event"] == "done"
    html = frames[-1]["html"]
    assert "Comparison Summary" in html
    assert "Schema Comparison" in html
    assert "Row Count Comparison" in html
    assert "Column Profile Comparison" in html


def test_compare_all_stores_last_report(client, connected):
    from seatunnel_agent.agents.data.data_comparison.registry import (
        get_registry,
    )

    _compound(client, connected, "all")
    session = get_registry().get(connected)
    assert session is not None and session.last_report is not None
    assert session.last_report.schema is not None
    assert session.last_report.row_count is not None


def test_compare_all_optional_feature_stages(client, connected):
    """Skew/checksum/partition/custom-agg stages run when their options are set."""
    frames = _frames(_compound(
        client, connected, "all",
        skew_columns="val", checksum_columns="id, val",
        partition_col="val", expressions="total=SUM(id)").text)
    html = frames[-1]["html"]
    assert "Data Skew Analysis" in html
    assert "Checksum Comparison" in html
    assert "Partition Comparison" in html
    assert "Custom Aggregate Comparison" in html


def test_compare_all_guard_not_connected(client):
    sid = _session(client)
    frames = _frames(_compound(client, sid, "all").text)
    assert frames == [
        {"event": "done",
         "html": "Please connect both data sources first"}]


def test_compare_all_guard_where_ddl(client, connected):
    frames = _frames(_compound(client, connected, "all",
                               where="1=1; DROP TABLE x").text)
    assert frames[-1]["event"] == "done"
    assert "forbidden keyword" in frames[-1]["html"]


def test_compare_all_409_when_running(client, connected, monkeypatch):
    from seatunnel_agent.agents.data.data_comparison import compound

    started = threading.Event()
    release = threading.Event()
    orig = compound.profile_inner

    def slow(*args, **kwargs):
        started.set()
        assert release.wait(10)
        return orig(*args, **kwargs)

    monkeypatch.setattr(compound, "profile_inner", slow)

    result: dict = {}

    def run() -> None:
        result["r"] = _compound(client, connected, "all")

    th = threading.Thread(target=run)
    th.start()
    try:
        assert started.wait(10), "first run never started"
        r2 = _compound(client, connected, "all")
        assert r2.status_code == 409
        # the guard also covers the other compound actions of the session
        r3 = _compound(client, connected, "batch-count")
        assert r3.status_code == 409
    finally:
        release.set()
        th.join(30)
    assert result["r"].status_code == 200
    assert _frames(result["r"].text)[-1]["event"] == "done"


def test_compare_all_unknown_session_404(client):
    assert _compound(client, "nope", "all").status_code == 404


def test_batch_count_progress_per_table_and_card(client, connected):
    r = _compound(client, connected, "batch-count")
    assert r.status_code == 200
    frames = _frames(r.text)
    progress = [f for f in frames if f["event"] == "progress"]
    # one common table (orders) -> one per-table progress frame
    assert len(progress) == 1
    assert "orders" in progress[0]["desc"]
    assert progress[0]["value"] == 1.0
    assert frames[-1]["event"] == "done"
    assert "Batch Row Count" in frames[-1]["html"]


def test_batch_full_streams_and_renders_card(client, connected):
    r = _compound(client, connected, "batch-full", threshold="60%")
    assert r.status_code == 200
    frames = _frames(r.text)
    assert any(f["event"] == "progress" for f in frames)
    assert frames[-1]["event"] == "done"
    html = frames[-1]["html"]
    assert "Batch Full Comparison" in html
    assert "orders" in html


def test_batch_guard_not_connected(client):
    sid = _session(client)
    frames = _frames(_compound(client, sid, "batch-count").text)
    assert frames == [
        {"event": "done",
         "html": "Please connect both data sources first"}]


def test_profile_card(client, connected):
    r = _compound(client, connected, "profile")
    assert r.status_code == 200
    html = r.json()["html"]
    assert "Column Profile Comparison" in html


def test_profile_guard_not_connected(client):
    sid = _session(client)
    html = _compound(client, sid, "profile").json()["html"]
    assert html == "Please connect both data sources first"


# ── ticket 08: generation + templates ───────────────────────────────


@pytest.fixture()
def templates_tmp(tmp_path, monkeypatch):
    """Point the generation router's templates store at tmp_path."""
    from seatunnel_agent.agents.data.data_comparison import (
        generation as gen_mod,
    )
    from seatunnel_agent.agents.data.data_comparison.templates_store import (
        ComparisonTemplatesStore,
    )

    store = ComparisonTemplatesStore(tmp_path / "dc_templates.json")
    monkeypatch.setattr(gen_mod, "_TEMPLATES_STORE", store)
    return store


@pytest.fixture()
def gen_presets_tmp(presets_tmp, monkeypatch):
    """Multi-env compare resolves presets via the generation module."""
    from seatunnel_agent.agents.data.data_comparison import (
        generation as gen_mod,
    )

    monkeypatch.setattr(gen_mod, "_PRESETS_STORE", presets_tmp)
    return presets_tmp


def _set_passwords(sid: str, pw_a: str, pw_b: str) -> None:
    from seatunnel_agent.agents.data.data_comparison.registry import (
        get_registry,
    )

    session = get_registry().get(sid)
    assert session is not None
    with session.lock:
        session.executor_a.config.password = pw_a
        session.executor_b.config.password = pw_b


# ── sync-config generation + download ───────────────────────────────


def test_sync_config_masked_html_real_password_in_download(client, connected):
    _set_passwords(connected, "pw-a-secret", "pw-b-secret")
    r = client.post("/api/datacompare/generate/sync-config",
                    json={"session_id": connected, "table_a": "orders",
                          "table_b": "orders", "lang": "en"})
    assert r.status_code == 200
    data = r.json()
    assert "Sync config generated" in data["html"]
    # rendered HTML masks the passwords
    assert "******" in data["html"]
    assert "pw-a-secret" not in data["html"]
    assert data["download_id"]

    d = client.get("/api/datacompare/generate/sync-config/download",
                   params={"id": data["download_id"]})
    assert d.status_code == 200
    assert "attachment" in d.headers.get("content-disposition", "")
    # downloaded .conf carries the real passwords, not the mask
    assert 'password = "pw-a-secret"' in d.text
    assert 'password = "pw-b-secret"' in d.text
    assert "******" not in d.text
    assert 'job.mode = "BATCH"' in d.text


def test_sync_config_guard_not_connected(client):
    sid = _session(client)
    data = client.post("/api/datacompare/generate/sync-config",
                       json={"session_id": sid, "table_a": "orders",
                             "table_b": "orders", "lang": "en"}).json()
    assert data["html"] == "Please connect both data sources first"
    assert data["download_id"] is None


def test_sync_config_download_unknown_id_404(client):
    r = client.get("/api/datacompare/generate/sync-config/download",
                   params={"id": "nope"})
    assert r.status_code == 404


# ── diff-SQL generation ─────────────────────────────────────────────


def test_diff_sql_requires_keyed_diff(client, connected):
    data = client.post("/api/datacompare/generate/diff-sql",
                       json={"session_id": connected, "table_a": "orders",
                             "table_b": "orders", "lang": "en"}).json()
    assert data["html"] == "No keyed diff result to generate SQL from"


def test_diff_sql_from_keyed_diff(client, connected):
    # a keyed sample diff populates session.last_report.keyed_diff
    _action(client, connected, "sample", key_columns="id")
    html = client.post("/api/datacompare/generate/diff-sql",
                       json={"session_id": connected, "table_a": "orders",
                             "table_b": "orders", "lang": "en"}).json()["html"]
    assert "Generated SQL" in html
    assert "INSERT INTO" in html or "DELETE FROM" in html


# ── lineage from SQL ────────────────────────────────────────────────


def test_lineage_upstream_tables(client):
    html = client.post(
        "/api/datacompare/lineage",
        json={"table": "orders", "lang": "en",
              "sqls": "INSERT INTO orders SELECT * FROM raw_orders"},
    ).json()["html"]
    assert "Upstream Dependencies" in html
    assert "raw_orders" in html


def test_lineage_empty_sql_hint(client):
    html = client.post(
        "/api/datacompare/lineage",
        json={"table": "orders", "sqls": "", "lang": "en"},
    ).json()["html"]
    assert html == "SQL statements to trace lineage from (one per line)"


def test_lineage_no_table_hint(client):
    html = client.post(
        "/api/datacompare/lineage",
        json={"table": "", "sqls": "SELECT 1", "lang": "en"},
    ).json()["html"]
    assert html == "Please select tables on both sides"


# ── multi-environment compare ───────────────────────────────────────


def test_compare_environments_smoke(client, gen_presets_tmp, db_a, db_b):
    _save_preset(client, name="dev-sqlite", ds_type="sqlite", host="",
                 port=0, database=db_a, username="", password="",
                 environment="dev")
    _save_preset(client, name="prod-sqlite", ds_type="sqlite", host="",
                 port=0, database=db_b, username="", password="",
                 environment="prod")
    html = client.post(
        "/api/datacompare/compare/environments",
        json={"env_a": "dev", "env_b": "prod", "table": "orders",
              "where": "", "lang": "en"},
    ).json()["html"]
    assert "Multi-Environment Result" in html
    assert "Row Count Comparison" in html
    assert "Schema Comparison" in html
    assert "Aggregate Comparison" in html
    # recolored header: the legacy indigo is forbidden on this page
    assert "#6366f1" not in html


def test_compare_environments_unknown_env_hint(client, gen_presets_tmp):
    html = client.post(
        "/api/datacompare/compare/environments",
        json={"env_a": "dev", "env_b": "prod", "table": "orders",
              "where": "", "lang": "en"},
    ).json()["html"]
    assert html == "e.g. dev, staging, prod"


def test_compare_environments_where_ddl_rejected(client, gen_presets_tmp):
    html = client.post(
        "/api/datacompare/compare/environments",
        json={"env_a": "dev", "env_b": "prod", "table": "orders",
              "where": "1=1; DROP TABLE x", "lang": "en"},
    ).json()["html"]
    assert "forbidden keyword" in html


# ── templates CRUD ──────────────────────────────────────────────────


def _save_template(client, **kw):
    body = {"name": "t1", "table_a": "orders", "table_b": "orders",
            "where_clause": "id = 1", "key_columns": "id",
            "threshold": "5%", "column_mapping": "",
            "sample_strategy": "TOP N", "watermark_column": "",
            "quality_rules": "", "webhook_url": "",
            "notify_on_fail": False, "masking_enabled": True}
    body.update(kw)
    return client.post("/api/datacompare/templates", json=body)


def test_templates_list_empty(client, templates_tmp):
    r = client.get("/api/datacompare/templates")
    assert r.status_code == 200
    assert r.json()["templates"] == []


def test_templates_save_load_delete_round_trip(client, templates_tmp):
    assert _save_template(client).json()["ok"] is True

    listed = client.get("/api/datacompare/templates").json()["templates"]
    assert [t["name"] for t in listed] == ["t1"]

    full = client.get("/api/datacompare/templates/t1").json()
    assert full["table_a"] == "orders"
    assert full["where_clause"] == "id = 1"
    assert full["key_columns"] == "id"
    assert full["threshold"] == "5%"
    assert full["sample_strategy"] == "TOP N"
    assert full["masking_enabled"] is True

    assert client.delete("/api/datacompare/templates/t1").json()["ok"] is True
    assert client.get("/api/datacompare/templates").json()["templates"] == []


def test_templates_save_empty_name_rejected(client, templates_tmp):
    assert _save_template(client, name="  ").status_code == 400


def test_templates_load_unknown_404(client, templates_tmp):
    assert client.get("/api/datacompare/templates/nope").status_code == 404


def test_templates_delete_unknown_404(client, templates_tmp):
    assert client.delete("/api/datacompare/templates/nope").status_code == 404


# ── templates batch run ─────────────────────────────────────────────


def test_templates_batch_run_combined_card(client, templates_tmp, connected):
    # where "id = 1" makes counts match (1/1) on both sides -> Pass
    _save_template(client, name="t1")
    html = client.post("/api/datacompare/templates/batch-run",
                       json={"session_id": connected, "names": ["t1"],
                             "lang": "en"}).json()["html"]
    assert "Batch Template Results" in html
    assert "t1" in html
    assert "Pass" in html


def test_templates_batch_run_guards(client, templates_tmp, connected):
    # no names selected -> hint
    html = client.post("/api/datacompare/templates/batch-run",
                       json={"session_id": connected, "names": [],
                             "lang": "en"}).json()["html"]
    assert html == "Select templates to run in batch"
    # not connected -> connect-both guard
    sid = _session(client)
    html = client.post("/api/datacompare/templates/batch-run",
                       json={"session_id": sid, "names": ["t1"],
                             "lang": "en"}).json()["html"]
    assert html == "Please connect both data sources first"
