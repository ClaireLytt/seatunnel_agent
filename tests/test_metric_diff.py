# -*- coding: utf-8 -*-
"""Tests for the metric consistency checker (metric_diff).

Deterministic only — no database, no LLM.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.metric_diff import (
    canonical_expr,
    check_sql_dir,
    render_markdown,
    report_to_dict,
)

runner = CliRunner()

DEMO = Path(__file__).resolve().parents[1] / "examples" / "metricdiff_demo"


def _write(tmp_path, name, text):
    (tmp_path / name).write_text(text, encoding="utf-8")


def _conflict(report, name):
    return next((c for c in report.conflicts if c.name == name), None)


# ─────────────────────────── canonicalization ───────────────────────────

@pytest.mark.parametrize("a,b", [
    ("SUM(o.amount) AS gmv", "sum(amount)"),
    ("COUNT(1)", "count(*)"),
    ("u.phone", "phone"),
    ("SUM( o.amount )", "SUM(amount) AS x"),
])
def test_canonical_expr_equivalent(a, b):
    assert canonical_expr(a) == canonical_expr(b)


@pytest.mark.parametrize("a,b", [
    ("SUM(amount)", "SUM(amount - refund)"),
    ("phone", "email"),
])
def test_canonical_expr_different(a, b):
    assert canonical_expr(a) != canonical_expr(b)


def test_canonical_expr_unparseable_falls_back():
    # regex fallback still strips qualifiers and uppercases
    assert canonical_expr("o.amount ::weird") == \
        canonical_expr("amount ::weird")


# ─────────────────────────── conflict detection ───────────────────────────

def test_expr_conflict_is_high(tmp_path):
    _write(tmp_path, "a.sql",
           "INSERT OVERWRITE TABLE ads.a SELECT sum(amount) AS gmv "
           "FROM dwd.o;")
    _write(tmp_path, "b.sql",
           "INSERT OVERWRITE TABLE ads.b SELECT sum(amount - refund) AS gmv "
           "FROM dwd.o;")
    report = check_sql_dir(tmp_path)
    c = _conflict(report, "gmv")
    assert c is not None and c.severity == "high"
    assert c.kind == "expr_conflict"
    assert {d.table for d in c.defs} == {"ads.a", "ads.b"}


def test_source_conflict_is_medium(tmp_path):
    _write(tmp_path, "a.sql",
           "INSERT OVERWRITE TABLE ads.a SELECT u.phone AS contact "
           "FROM dwd.u u;")
    _write(tmp_path, "b.sql",
           "INSERT OVERWRITE TABLE ads.b SELECT u.email AS contact "
           "FROM dwd.u u;")
    report = check_sql_dir(tmp_path)
    c = _conflict(report, "contact")
    assert c is not None and c.severity == "medium"
    assert c.kind == "source_conflict"


def test_count_one_equals_count_star(tmp_path):
    _write(tmp_path, "a.sql",
           "INSERT OVERWRITE TABLE ads.a SELECT count(1) AS cnt FROM dwd.o;")
    _write(tmp_path, "b.sql",
           "INSERT OVERWRITE TABLE ads.b SELECT count(*) AS cnt FROM dwd.o;")
    report = check_sql_dir(tmp_path)
    assert _conflict(report, "cnt") is None


def test_identical_formulas_consistent(tmp_path):
    _write(tmp_path, "a.sql",
           "INSERT OVERWRITE TABLE ads.a SELECT SUM(o.amount) AS gmv "
           "FROM dwd.o o;")
    _write(tmp_path, "b.sql",
           "INSERT OVERWRITE TABLE ads.b SELECT sum(amount) AS gmv "
           "FROM dwd.o;")
    report = check_sql_dir(tmp_path)
    assert not report.conflicts
    assert report.consistent >= 1


def test_same_name_copies_from_same_column_pass(tmp_path):
    _write(tmp_path, "a.sql",
           "INSERT OVERWRITE TABLE ads.a SELECT user_id FROM dwd.u;")
    _write(tmp_path, "b.sql",
           "INSERT OVERWRITE TABLE ads.b SELECT user_id FROM dwd.o;")
    report = check_sql_dir(tmp_path)
    assert _conflict(report, "user_id") is None


def test_single_definition_never_conflicts(tmp_path):
    _write(tmp_path, "a.sql",
           "INSERT OVERWRITE TABLE ads.a SELECT sum(x) AS only_here "
           "FROM dwd.o;")
    report = check_sql_dir(tmp_path)
    assert not report.conflicts


# ─────────────────────────── demo dir ───────────────────────────

def test_demo_dir():
    report = check_sql_dir(DEMO)
    c = report.counts()
    assert c["high"] == 1          # gmv formulas differ
    assert c["medium"] == 1        # contact ← phone vs email
    assert _conflict(report, "order_cnt") is None  # count(1) ≡ count(*)


def test_empty_dir(tmp_path):
    report = check_sql_dir(tmp_path)
    assert not report.conflicts
    assert report.warnings


# ─────────────────────────── rendering ───────────────────────────

def test_render_markdown_zh_and_en():
    report = check_sql_dir(DEMO)
    zh = render_markdown(report, "zh")
    en = render_markdown(report, "en")
    assert "指标口径一致性检查" in zh and "计算公式不同" in zh
    assert "Metric Consistency Check" in en and "different formulas" in en
    assert "01_gmv_report_a.sql" in zh      # origin files surface


def test_report_to_dict_is_json_serializable():
    data = report_to_dict(check_sql_dir(DEMO), "en")
    assert data["counts"]["high"] == 1
    json.dumps(data)


# ─────────────────────────── CLI ───────────────────────────

def test_cli_metricdiff():
    r = runner.invoke(cli, ["metricdiff", "--sql-dir", str(DEMO)])
    assert r.exit_code == 0, r.output
    assert "指标口径一致性" in r.output


def test_cli_metricdiff_fail_on(tmp_path):
    out = tmp_path / "md.json"
    r = runner.invoke(cli, ["metricdiff", "--sql-dir", str(DEMO),
                            "-F", "json", "--fail-on", "high",
                            "-o", str(out)])
    assert r.exit_code == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["counts"]["high"] == 1


def test_cli_metricdiff_clean_passes(tmp_path):
    (tmp_path / "a.sql").write_text(
        "INSERT OVERWRITE TABLE ads.a SELECT sum(x) AS m FROM dwd.o;",
        encoding="utf-8")
    r = runner.invoke(cli, ["metricdiff", "--sql-dir", str(tmp_path),
                            "--fail-on", "medium"])
    assert r.exit_code == 0, r.output


# ─────────────────────────── REST API ───────────────────────────

@pytest.fixture()
def api_client():
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.metric_diff.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_check(api_client):
    r = api_client.post("/api/metricdiff/check", json={
        "sql_dir": str(DEMO), "lang": "en", "report": True})
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["counts"]["high"] == 1
    assert "Metric Consistency Check" in data["report"]


def test_api_check_outside_whitelist(api_client, monkeypatch, tmp_path):
    monkeypatch.setenv("METRICDIFF_API_ALLOWED_DIRS",
                       str(tmp_path / "only_here"))
    r = api_client.post("/api/metricdiff/check", json={"sql_dir": str(DEMO)})
    assert r.status_code == 403


def test_api_check_bad_dir(api_client):
    r = api_client.post("/api/metricdiff/check", json={"sql_dir": "no_such"})
    assert r.status_code == 400
    assert api_client.get("/api/metricdiff/health").json()["status"] == "ok"
