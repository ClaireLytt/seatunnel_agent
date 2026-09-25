# -*- coding: utf-8 -*-
"""Tests for the SQL dialect translation agent (sql_transpile).

Deterministic only — no LLM, no database, no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.sql_transpile import (
    DIALECTS,
    infer_dialect,
    normalize_dialect,
    render_batch_markdown,
    render_markdown,
    result_to_dict,
    translate,
    transpile_dir,
)

runner = CliRunner()

DEMO_DIR = Path(__file__).resolve().parents[1] / "examples" / "transpile_demo"


# ─────────────────────────── dialect handling ───────────────────────────

def test_dialect_matrix():
    assert DIALECTS == ("hive", "spark", "doris", "starrocks")


@pytest.mark.parametrize("alias,canon", [
    ("hive", "hive"), ("HiveQL", "hive"), ("sparksql", "spark"),
    ("Spark", "spark"), ("sr", "starrocks"), ("DORIS", "doris"),
])
def test_normalize_dialect_aliases(alias, canon):
    assert normalize_dialect(alias) == canon


def test_normalize_dialect_rejects_unknown():
    with pytest.raises(ValueError, match="unsupported dialect"):
        normalize_dialect("flink")


def test_infer_dialect_defaults_to_hive():
    assert infer_dialect("SELECT a FROM t") == "hive"
    r = translate("SELECT 1", dst="doris")
    assert r.src_inferred and r.src_dialect == "hive"


# ─────────────────────────── golden translations ───────────────────────────
# Each case: (src, dst, input SQL, fragment expected in the output).

GOLDEN = [
    # hive → doris
    ("hive", "doris", "SELECT get_json_object(p, '$.a') FROM t", "JSON_EXTRACT("),
    ("hive", "doris", "SELECT split(s, ',') FROM t", "SPLIT_BY_STRING("),
    ("hive", "doris", "SELECT CAST(a AS STRING) FROM t", "CAST(a AS STRING)"),
    ("hive", "doris", "SELECT date_add('2024-01-01', 1)", "DATE_ADD("),
    ("hive", "doris",
     "SELECT ROW_NUMBER() OVER (PARTITION BY a ORDER BY b) FROM t",
     "ROW_NUMBER() OVER"),
    ("hive", "doris", "SELECT COUNT(DISTINCT a) FROM t GROUP BY b",
     "COUNT(DISTINCT a)"),
    ("hive", "doris", "SELECT a FROM t WHERE dt BETWEEN '1' AND '2'",
     "BETWEEN '1' AND '2'"),
    ("hive", "doris", "SELECT nvl(a, 0) FROM t", "COALESCE(a, 0)"),
    # hive → starrocks
    ("hive", "starrocks", "SELECT get_json_object(p, '$.a') FROM t",
     "->> '$.a'"),
    ("hive", "starrocks", "SELECT collect_list(a) FROM t GROUP BY b",
     "ARRAY_AGG("),
    ("hive", "starrocks", "SELECT a FROM t LIMIT 10", "LIMIT 10"),
    # spark → hive / doris
    ("spark", "hive", "SELECT a FROM t WHERE b ILIKE '%x%'", "LOWER(b) LIKE"),
    ("spark", "doris", "SELECT try_cast(a AS INT) FROM t", "CAST("),
    # doris/starrocks → hive/spark (reverse direction)
    ("doris", "hive", "SELECT JSON_EXTRACT(p, '$.a') FROM t",
     "GET_JSON_OBJECT("),
    ("starrocks", "spark", "SELECT a FROM t", "SELECT"),
]


@pytest.mark.parametrize("src,dst,sql,expect", GOLDEN)
def test_golden_translation(src, dst, sql, expect):
    r = translate(sql, dst=dst, src=src)
    assert len(r.statements) == 1
    s = r.statements[0]
    assert s.ok, [i.to_dict() for i in s.issues]
    assert expect.casefold() in s.output_sql.casefold(), s.output_sql


def test_translation_is_deterministic():
    sql = "SELECT get_json_object(p,'$.a'), my_udf(x) FROM t"
    a = translate(sql, dst="doris", src="hive")
    b = translate(sql, dst="doris", src="hive")
    assert a.to_dict()["statements"] == b.to_dict()["statements"]


# ─────────────────────────── incompatibility issues ───────────────────────────

def test_parse_error_is_isolated_per_statement():
    sql = "SELECT 1;\nSELECT FROM WHERE;\nSELECT 2;"
    r = translate(sql, dst="doris", src="hive")
    assert [s.ok for s in r.statements] == [True, False, True]
    bad = r.statements[1]
    assert bad.issues[0].kind == "parse_error"
    assert bad.issues[0].level == "error"
    assert r.counts() == {"total": 3, "auto": 2, "manual": 0, "failed": 1}


def test_parse_error_message_is_cleaned():
    r = translate("SELECT FROM WHERE", dst="doris", src="hive")
    err = r.statements[0].issues[0].params["error"]
    assert "<Token" not in err
    assert "line" in err.lower() or "col" in err.lower()


def test_unknown_function_flagged_as_warn():
    r = translate("SELECT my_udf(a), my_udf(b) FROM t", dst="doris", src="hive")
    issues = [i for i in r.statements[0].issues if i.kind == "unknown_function"]
    assert len(issues) == 1  # deduplicated per statement
    assert issues[0].level == "warn"
    assert issues[0].params["func"].lower() == "my_udf"
    assert not r.statements[0].auto  # warn ⇒ manual


def test_known_function_not_flagged():
    r = translate("SELECT get_json_object(p,'$.a') FROM t",
                  dst="doris", src="hive")
    assert r.statements[0].auto


def test_write_hints_flagged_for_mpp_targets_only():
    sql = "SELECT a FROM t DISTRIBUTE BY a SORT BY a"
    r = translate(sql, dst="doris", src="hive")
    kinds = [i.kind for i in r.statements[0].issues]
    assert kinds.count("write_hint") == 2
    assert all(i.level == "info" for i in r.statements[0].issues)
    assert r.statements[0].auto  # info-only stays fully automatic
    # hive → spark keeps the semantics: no hint issues
    r2 = translate(sql, dst="spark", src="hive")
    assert not [i for i in r2.statements[0].issues if i.kind == "write_hint"]


def test_lateral_view_and_insert_partition_notes():
    sql = ("INSERT OVERWRITE TABLE t PARTITION (dt='1') "
           "SELECT item FROM s LATERAL VIEW explode(xs) x AS item")
    r = translate(sql, dst="starrocks", src="hive")
    kinds = {i.kind for i in r.statements[0].issues}
    assert {"lateral_view", "insert_partition"} <= kinds


def test_storage_clause_flagged_on_create():
    sql = ("CREATE TABLE t (a INT) STORED AS ORC "
           "TBLPROPERTIES ('k'='v')")
    r = translate(sql, dst="doris", src="hive")
    issues = [i for i in r.statements[0].issues if i.kind == "storage_clause"]
    assert issues and issues[0].level == "warn"
    assert "STORED AS" in issues[0].params["clauses"]
    assert "TBLPROPERTIES" in issues[0].params["clauses"]


def test_issue_levels_sorted_most_severe_first():
    sql = ("SELECT my_udf(a), item FROM t "
           "LATERAL VIEW explode(xs) x AS item DISTRIBUTE BY a")
    r = translate(sql, dst="doris", src="hive")
    levels = [i.level for i in r.statements[0].issues]
    assert levels == sorted(levels, key=("error", "warn", "info").index)


# ─────────────────────────── report rendering ───────────────────────────

def test_render_markdown_zh_and_en():
    r = translate("SELECT my_udf(a) FROM t", dst="doris", src="hive")
    zh = render_markdown(r, "zh")
    assert "未知函数 my_udf" in zh
    assert "需人工 1" in zh
    en = render_markdown(r, "en")
    assert "Unknown function my_udf" in en
    assert "manual 1" in en


def test_render_markdown_clean_result():
    r = translate("SELECT 1", dst="doris", src="hive")
    md = render_markdown(r, "zh")
    assert "未发现不兼容点" in md
    assert "全自动 1" in md


def test_result_to_dict_carries_rendered_messages():
    r = translate("SELECT my_udf(a) FROM t", dst="doris", src="hive")
    data = result_to_dict(r, "en")
    issue = data["statements"][0]["issues"][0]
    assert issue["kind"] == "unknown_function"
    assert "Unknown function" in issue["message"]
    assert data["stats"] == {"total": 1, "auto": 0, "manual": 1, "failed": 0}


def test_output_script_keeps_failed_statement_as_comment():
    r = translate("SELECT 1;\nSELECT FROM WHERE;", dst="doris", src="hive")
    script = r.output_script()
    assert "-- transpile-error:" in script
    assert "SELECT FROM WHERE;" in script
    assert script.count(";") >= 2


# ─────────────────────────── batch / demo dir ───────────────────────────

def test_demo_dir_batch_counts(tmp_path):
    b = transpile_dir(DEMO_DIR, dst="doris", src="hive", out_dir=tmp_path)
    assert b.counts() == {"files": 6, "total": 6, "auto": 3,
                          "manual": 2, "failed": 1}
    assert b.worst_level() == "error"
    # mirrored outputs exist for every input, including the broken one
    for f in b.files:
        assert f.out_path and Path(f.out_path).is_file()
    broken = (tmp_path / "06_broken.sql").read_text(encoding="utf-8")
    assert "-- transpile-error:" in broken


def test_batch_without_out_dir_writes_nothing(tmp_path):
    before = sorted(DEMO_DIR.rglob("*"))
    b = transpile_dir(DEMO_DIR, dst="starrocks", src="hive")
    assert b.out_dir is None
    assert all(f.out_path is None for f in b.files)
    assert sorted(DEMO_DIR.rglob("*")) == before


def test_batch_mirrors_nested_dirs(tmp_path):
    src_root = tmp_path / "in"
    (src_root / "sub").mkdir(parents=True)
    (src_root / "a.sql").write_text("SELECT 1;", encoding="utf-8")
    (src_root / "sub" / "b.sql").write_text("SELECT 2;", encoding="utf-8")
    out_root = tmp_path / "out"
    b = transpile_dir(src_root, dst="doris", src="hive", out_dir=out_root)
    assert (out_root / "a.sql").is_file()
    assert (out_root / "sub" / "b.sql").is_file()
    assert b.counts()["files"] == 2


def test_batch_rejects_non_directory(tmp_path):
    f = tmp_path / "x.sql"
    f.write_text("SELECT 1", encoding="utf-8")
    with pytest.raises(ValueError, match="not a directory"):
        transpile_dir(f, dst="doris")


def test_batch_render_markdown():
    b = transpile_dir(DEMO_DIR, dst="doris", src="hive")
    md = render_batch_markdown(b, "zh")
    assert "06_broken.sql" in md
    assert "文件 6" in md


# ─────────────────────────── CLI ───────────────────────────

def test_cli_inline_translation():
    res = runner.invoke(cli, [
        "transpile", "--from", "hive", "--to", "doris",
        "-s", "SELECT get_json_object(p,'$.a') FROM t", "--no-llm",
    ])
    assert res.exit_code == 0, res.output
    assert "JSON_EXTRACT" in res.output


def test_cli_requires_a_source():
    res = runner.invoke(cli, ["transpile", "--to", "doris"])
    assert res.exit_code != 0
    assert "Provide SQL" in res.output


def test_cli_json_format():
    res = runner.invoke(cli, [
        "transpile", "--from", "hive", "--to", "doris",
        "-s", "SELECT my_udf(a) FROM t", "-F", "json", "--no-llm",
    ])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert data["stats"]["manual"] == 1
    assert data["statements"][0]["issues"][0]["kind"] == "unknown_function"


def test_cli_fail_on_gate():
    ok = runner.invoke(cli, [
        "transpile", "--from", "hive", "--to", "doris",
        "-s", "SELECT 1", "--no-llm", "--fail-on", "error",
    ])
    assert ok.exit_code == 0
    bad = runner.invoke(cli, [
        "transpile", "--from", "hive", "--to", "doris",
        "-s", "SELECT FROM WHERE", "--no-llm", "--fail-on", "error",
    ])
    assert bad.exit_code == 1
    # warn gate trips on manual findings too
    warn = runner.invoke(cli, [
        "transpile", "--from", "hive", "--to", "doris",
        "-s", "SELECT my_udf(a) FROM t", "--no-llm", "--fail-on", "warn",
    ])
    assert warn.exit_code == 1


def test_cli_batch_dir(tmp_path):
    res = runner.invoke(cli, [
        "transpile", "--from", "hive", "--to", "starrocks",
        "-D", str(DEMO_DIR), "-o", str(tmp_path), "--no-llm",
    ])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "03_dws_gmv.sql").is_file()


def test_cli_single_file_with_out(tmp_path):
    out = tmp_path / "translated.sql"
    res = runner.invoke(cli, [
        "transpile", "--from", "hive", "--to", "doris",
        str(DEMO_DIR / "03_dws_gmv.sql"), "-o", str(out), "--no-llm",
    ])
    assert res.exit_code == 0, res.output
    assert "SUM(amount)" in out.read_text(encoding="utf-8")

# ─────────────────────────── REST API ───────────────────────────

@pytest.fixture()
def api_client():
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from seatunnel_agent.sql_transpile.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_translate(api_client):
    r = api_client.post("/api/transpile/translate", json={
        "sql": "SELECT get_json_object(p,'$.a') FROM t",
        "from": "hive", "to": "doris",
    })
    assert r.status_code == 200
    data = r.json()
    assert "JSON_EXTRACT" in data["output_sql"]
    assert data["stats"]["auto"] == 1
    assert data["src_dialect"] == "hive" and not data["src_inferred"]


def test_api_translate_infers_source_and_renders_report(api_client):
    r = api_client.post("/api/transpile/translate", json={
        "sql": "SELECT my_udf(a) FROM t", "to": "starrocks",
        "report": True, "lang": "en",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["src_inferred"]
    assert "Unknown function" in data["report"]


def test_api_translate_rejects_bad_dialect(api_client):
    r = api_client.post("/api/transpile/translate", json={
        "sql": "SELECT 1", "to": "flink",
    })
    assert r.status_code == 400
    assert "unsupported dialect" in r.json()["detail"]


def test_api_batch_reads_demo_dir(api_client, monkeypatch):
    monkeypatch.setenv("TRANSPILE_API_ALLOWED_DIRS", str(DEMO_DIR))
    r = api_client.post("/api/transpile/batch", json={
        "dir": str(DEMO_DIR), "from": "hive", "to": "doris",
    })
    assert r.status_code == 200
    assert r.json()["stats"] == {"files": 6, "total": 6, "auto": 3,
                                 "manual": 2, "failed": 1}


def test_api_batch_rejects_dir_outside_whitelist(api_client, monkeypatch, tmp_path):
    monkeypatch.setenv("TRANSPILE_API_ALLOWED_DIRS", str(tmp_path))
    r = api_client.post("/api/transpile/batch", json={
        "dir": str(DEMO_DIR), "to": "doris",
    })
    assert r.status_code == 403


def test_api_batch_never_writes(api_client, monkeypatch):
    monkeypatch.setenv("TRANSPILE_API_ALLOWED_DIRS", str(DEMO_DIR))
    before = sorted(p.name for p in DEMO_DIR.rglob("*"))
    r = api_client.post("/api/transpile/batch", json={
        "dir": str(DEMO_DIR), "to": "starrocks",
    })
    assert r.status_code == 200
    assert sorted(p.name for p in DEMO_DIR.rglob("*")) == before


def test_api_dialects_and_health(api_client):
    assert api_client.get("/api/transpile/health").json() == {"status": "ok"}
    d = api_client.get("/api/transpile/dialects").json()
    assert d["dialects"] == ["hive", "spark", "doris", "starrocks"]
