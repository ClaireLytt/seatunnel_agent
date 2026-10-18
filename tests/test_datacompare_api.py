"""In-process tests for the Data Comparison REST API (ticket 02).

Seam: the HTTP contract of /api/datacompare (session create, meta,
per-side connect, tables listing) — never the internals of the
registry or the executors. Real connections are exercised against
file-backed SQLite fixtures.
"""

from __future__ import annotations

import sqlite3

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
