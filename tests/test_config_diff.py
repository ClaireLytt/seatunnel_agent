"""Tests for the config-diff agent (58): differ, report, API, CLI."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.agents.data.config_diff import (
    diff_configs,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "configdiff_demo"
DEV = (DEMO / "dev.conf").read_text("utf-8")
PROD = (DEMO / "prod.conf").read_text("utf-8")


# ── differ ───────────────────────────────────────────────────────────

def test_demo_diff_grading():
    result = diff_configs(DEV, PROD)
    assert result.left_keys == 9 and result.right_keys == 10
    by_key = {e.key: e for e in result.entries}
    assert by_key["env.parallelism"].severity == "high"
    assert by_key["env.parallelism"].kind == "changed"
    assert by_key["env.checkpoint.interval"].kind == "added"
    assert by_key["sink.Doris.batch_size"].kind == "removed"
    assert by_key["sink.Doris.batch_size"].severity == "mid"


def test_secrets_masked_but_counted():
    result = diff_configs(DEV, PROD)
    pw = next(e for e in result.entries
              if e.key == "source.Jdbc.password")
    assert pw.old == "***" and pw.new == "***"
    assert pw.kind == "changed"


def test_comments_and_order_ignored():
    a = 'env { parallelism = 2 }\nsink { t { x = 1 } }'
    b = ('# a comment\nsink { t { x = 1 } }\n'
         'env {\n  parallelism = 2  # same\n}')
    result = diff_configs(a, b)
    assert result.identical
    assert "identical" in render_markdown(result, lang="en")


def test_json_and_properties_parse():
    left = '{"env": {"parallelism": 2}}'
    right = "env.parallelism = 4"
    result = diff_configs(left, right)
    assert result.entries[0].key == "env.parallelism"
    assert result.entries[0].new == "4"


def test_list_values_flattened():
    a = '{"sink": {"pk": ["id"]}}'
    b = '{"sink": {"pk": ["id", "dt"]}}'
    result = diff_configs(a, b)
    assert any(e.key == "sink.pk[1]" and e.kind == "added"
               for e in result.entries)


def test_bad_config_rejected():
    import pytest

    with pytest.raises(ValueError):
        diff_configs("  ", PROD)
    with pytest.raises(ValueError):
        diff_configs("env { unclosed", PROD)


def test_entries_sorted_by_severity():
    sev = [e.severity for e in diff_configs(DEV, PROD).entries]
    order = {"high": 0, "mid": 1, "low": 2}
    assert sev == sorted(sev, key=order.__getitem__)


def test_report_both_langs():
    result = diff_configs(DEV, PROD)
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "配置漂移对比" in zh and "env.parallelism" in zh
    assert "Config Drift" in en and "***" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.config_diff import api as cd_api

    app = FastAPI()
    app.include_router(cd_api.router)
    return TestClient(app)


def test_api_diff_inline():
    res = _client().post("/api/configdiff/diff",
                         json={"left_text": DEV, "right_text": PROD,
                               "report": True, "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert len(body["result"]["entries"]) == 8
    assert "Config Drift" in body["report"]


def test_api_bad_config_400():
    res = _client().post("/api/configdiff/diff",
                         json={"left_text": "env { bad",
                               "right_text": PROD})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("CONFIGDIFF_API_ALLOWED_DIRS", str(DEMO))
    res = _client().post("/api/configdiff/diff", json={
        "left_file": str(DEMO / "dev.conf"),
        "right_file": str(DEMO / "prod.conf")})
    assert res.status_code == 200
    bad = _client().post("/api/configdiff/diff", json={
        "left_file": str(ROOT / "pyproject.toml"), "right_text": PROD})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.config_diff import advisor_llm

    monkeypatch.setattr(advisor_llm, "drift_note",
                        lambda result, lang="zh": "DIFF-NOTE")
    res = _client().post("/api/configdiff/diff",
                         json={"left_text": DEV, "right_text": PROD,
                               "llm": True, "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["drift_note"] == "DIFF-NOTE"


def test_api_health():
    body = _client().get("/api/configdiff/health").json()
    assert body == {"status": "ok", "agent": "config_diff"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_configdiff_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "configdiff", "-l", str(DEMO / "dev.conf"),
        "--right", str(DEMO / "prod.conf"), "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "配置漂移对比" in res.output and "env.parallelism" in res.output


def test_cli_fail_on_high_gate(tmp_path):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "configdiff", "-l", str(DEMO / "dev.conf"),
        "--right", str(DEMO / "prod.conf"), "--fail-on-high"])
    assert res.exit_code == 1
    same = tmp_path / "same.conf"
    same.write_text(DEV, encoding="utf-8")
    clean = CliRunner().invoke(cli, [
        "configdiff", "-l", str(same), "--right", str(same),
        "--fail-on-high"])
    assert clean.exit_code == 0, clean.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "config_diff" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.config_diff.tools import config_diff

    out = config_diff(DEV, PROD, lang="en")
    assert "Config Drift" in out and "env.parallelism" in out
    assert "required" in config_diff(" ", PROD)
    assert "bad input" in config_diff("env { bad", PROD)
