# -*- coding: utf-8 -*-
"""Tests for the SeaTunnel config deep linter (config_lint).

Deterministic only — no SeaTunnel installation, no database, no LLM.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.config_lint import (
    lint_dir,
    lint_file,
    lint_text,
    render_batch_markdown,
    render_markdown,
    result_to_dict,
)

runner = CliRunner()

DEMO = Path(__file__).resolve().parents[1] / "examples" / "conflint_demo"

OK_CONF = """
env { parallelism = 2, job.mode = "BATCH" }
source { FakeSource { result_table_name = "fake", rows = 10 } }
sink { Console { source_table_name = "fake" } }
"""


def _kinds(result):
    return {(f.kind, f.param or f.connector) for f in result.findings}


# ─────────────────────────── passing configs ───────────────────────────

def test_clean_config_passes():
    result = lint_text(OK_CONF)
    assert result.ok and not result.findings
    assert set(result.sections_found) >= {"env", "source", "sink"}
    assert "source:FakeSource" in result.connectors


def test_framework_keys_never_flagged():
    result = lint_text(
        'source { FakeSource { result_table_name = "x", parallelism = 2 } }'
        "\nsink { Console { source_table_name = \"x\" } }")
    assert not any(f.kind == "unknown_param" for f in result.findings)


# ─────────────────────────── structural errors ───────────────────────────

def test_syntax_error():
    result = lint_text("env { broken = ")
    assert not result.ok
    assert result.findings[0].kind == "syntax_error"


def test_missing_sections():
    result = lint_text("env { job.mode = \"BATCH\" }")
    kinds = {(f.kind, f.section) for f in result.findings}
    assert ("missing_section", "source") in kinds
    assert ("missing_section", "sink") in kinds


def test_empty_section():
    result = lint_text("source {}\nsink { Console {} }")
    assert any(f.kind == "empty_section" and f.section == "source"
               for f in result.findings)


# ─────────────────────────── connector checks ───────────────────────────

def test_unknown_connector_suggests():
    result = lint_text("source { FakeSource {} }\nsink { Consloe {} }")
    f = next(x for x in result.findings if x.kind == "unknown_connector")
    assert f.severity == "warn"
    assert f.message_params["suggestion"] == "Console"


def test_role_mismatch():
    result = lint_text("source { Console {} }\nsink { Console {} }")
    f = next(x for x in result.findings if x.kind == "role_mismatch")
    assert f.severity == "error" and f.section == "source"


def test_both_role_connector_never_flags():
    result = lint_text(
        'source { Jdbc { url="u", driver="d", user="u", password="p" } }\n'
        'sink { Jdbc { url="u", driver="d", user="u", password="p" } }')
    assert not any(f.kind == "role_mismatch" for f in result.findings)


def test_missing_required_param():
    result = lint_text(
        'source { Jdbc { url = "jdbc:mysql://h/db", driver = "d", '
        'user = "root" } }\nsink { Console {} }')
    missing = [f.param for f in result.findings
               if f.kind == "missing_required"]
    assert missing == ["password"]


def test_unknown_param_suggests():
    result = lint_text(
        'source { Jdbc { url="u", driver="d", user="u", password="p", '
        'quary = "SELECT 1" } }\nsink { Console {} }')
    f = next(x for x in result.findings if x.kind == "unknown_param")
    assert f.param == "quary"
    assert f.message_params["suggestion"] == "query"


def test_type_mismatch():
    result = lint_text(
        'source { FakeSource { rows = "ten" } }\nsink { Console {} }')
    f = next(x for x in result.findings if x.kind == "type_mismatch")
    assert f.param == "rows"
    assert f.message_params == {"declared": "int", "actual": "str"}


def test_unknown_transform_is_info_only():
    result = lint_text(
        "source { FakeSource {} }\n"
        "transform { Sql { query = \"SELECT 1\" } NoSuchTransform {} }\n"
        "sink { Console {} }")
    infos = [f for f in result.findings if f.section == "transform"]
    assert len(infos) == 1
    assert infos[0].severity == "info"
    assert infos[0].connector == "NoSuchTransform"


# ─────────────────────────── env checks ───────────────────────────

def test_bad_job_mode():
    result = lint_text(
        'env { job.mode = "batchy" }\n'
        "source { FakeSource {} }\nsink { Console {} }")
    assert any(f.kind == "bad_job_mode" for f in result.findings)


def test_cdc_requires_streaming():
    result = lint_text(
        'env { job.mode = "BATCH" }\n'
        'source { MySQL-CDC { hostname="h", port=3306, database-name="d", '
        'table-name="t", username="u", password="p" } }\n'
        "sink { Console {} }")
    assert any(f.kind == "cdc_requires_stream" for f in result.findings)


def test_cdc_with_streaming_passes():
    result = lint_text(
        'env { job.mode = "STREAMING" }\n'
        'source { MySQL-CDC { hostname="h", port=3306, database-name="d", '
        'table-name="t", username="u", password="p" } }\n'
        "sink { Console {} }")
    assert not any(f.kind == "cdc_requires_stream" for f in result.findings)


@pytest.mark.parametrize("value", ["0", "-1", "true", '"two"'])
def test_bad_parallelism(value):
    result = lint_text(
        f"env {{ parallelism = {value} }}\n"
        "source { FakeSource {} }\nsink { Console {} }")
    assert any(f.kind == "bad_parallelism" for f in result.findings)


# ─────────────────────────── files / demo dir ───────────────────────────

def test_demo_dir():
    results = lint_dir(DEMO)
    by_name = {Path(r.name).name: r for r in results}
    assert by_name["00_ok.conf"].ok
    assert not by_name["01_bad_params.conf"].ok
    assert not by_name["02_bad_mode.conf"].ok
    kinds = _kinds(by_name["02_bad_mode.conf"])
    assert ("cdc_requires_stream", "job.mode") in kinds
    assert ("bad_parallelism", "parallelism") in kinds


def test_lint_missing_file():
    result = lint_file("no_such_file.conf")
    assert not result.ok
    assert result.findings[0].kind == "syntax_error"


# ─────────────────────────── rendering ───────────────────────────

def test_render_markdown_zh_and_en():
    result = lint_text("source { Consloe {} }\nsink { Console {} }")
    zh = render_markdown(result, "zh")
    en = render_markdown(result, "en")
    assert "配置深度检查" in zh and "是不是想写" in zh
    assert "Config Lint" in en and "did you mean" in en


def test_render_batch_markdown():
    md = render_batch_markdown(lint_dir(DEMO), "zh")
    assert "文件 3" in md and "00_ok.conf" in md


def test_result_to_dict_is_json_serializable():
    data = result_to_dict(lint_text("source { Consloe {} }\nsink{Console{}}"))
    assert all("message" in f for f in data["findings"])
    json.dumps(data)


# ─────────────────────────── CLI ───────────────────────────

def test_cli_conflint_dir():
    r = runner.invoke(cli, ["conflint", "--dir", str(DEMO)])
    assert r.exit_code == 0, r.output
    assert "配置深度检查" in r.output


def test_cli_conflint_requires_source():
    r = runner.invoke(cli, ["conflint"])
    assert r.exit_code != 0


def test_cli_conflint_json_and_fail_on(tmp_path):
    out = tmp_path / "lint.json"
    r = runner.invoke(cli, ["conflint", "--dir", str(DEMO), "-F", "json",
                            "--fail-on", "error", "-o", str(out)])
    assert r.exit_code == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert any(x["counts"]["error"] for x in data)


def test_cli_conflint_clean_passes(tmp_path):
    p = tmp_path / "ok.conf"
    p.write_text(OK_CONF, encoding="utf-8")
    r = runner.invoke(cli, ["conflint", "--file", str(p),
                            "--fail-on", "warn"])
    assert r.exit_code == 0, r.output


# ─────────────────────────── REST API ───────────────────────────

@pytest.fixture()
def api_client():
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.config_lint.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_lint_inline(api_client):
    r = api_client.post("/api/conflint/lint", json={
        "config": "source { Consloe {} }\nsink { Console {} }",
        "lang": "en", "report": True})
    assert r.status_code == 200
    data = r.json()
    assert not data["results"][0]["ok"] or data["results"][0]["counts"]["warn"]
    assert "Config Lint" in data["report"]


def test_api_lint_dir_whitelisted(api_client):
    r = api_client.post("/api/conflint/lint", json={"dir": str(DEMO)})
    assert r.status_code == 200
    assert len(r.json()["results"]) == 3


def test_api_lint_dir_outside_whitelist(api_client, monkeypatch, tmp_path):
    monkeypatch.setenv("CONFLINT_API_ALLOWED_DIRS",
                       str(tmp_path / "only_here"))
    r = api_client.post("/api/conflint/lint", json={"dir": str(DEMO)})
    assert r.status_code == 403


def test_api_lint_requires_input(api_client):
    r = api_client.post("/api/conflint/lint", json={})
    assert r.status_code == 400
    assert api_client.get("/api/conflint/health").json()["status"] == "ok"
