# -*- coding: utf-8 -*-
"""CI triage: templates, clustering, flaky/drift analysis, CLI, API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.ci_inspect import (
    analyze,
    analyze_runs,
    cluster_logs,
    extract_error_lines,
    normalize_template,
    parse_runs,
    render_markdown,
)
from seatunnel_agent.cli import cli

DEMO = Path(__file__).resolve().parents[1] / "examples" / "ciinspect_demo"


class TestTemplates:
    def test_timestamp_and_volatiles_masked(self):
        line = ("2026-10-02T15:57:54.57Z ##[error]retry 3 failed for "
                "/home/runner/work/app/x.py at a1b2c3d4e5f6")
        tpl = normalize_template(line)
        assert "2026" not in tpl and "##[error]" not in tpl
        assert "<n>" in tpl and "<path>" in tpl and "<hash>" in tpl

    def test_same_root_cause_same_template(self):
        a = "ConnectionError: Failed to reach pypi.org:443 after 3 retries"
        b = "ConnectionError: Failed to reach pypi.org:443 after 5 retries"
        assert normalize_template(a) == normalize_template(b)

    def test_extract_error_lines(self):
        text = ("2026-10-02T15:57:51Z ok line\n"
                "2026-10-02T15:57:52Z ##[error]boom\n"
                "2026-10-02T15:57:53Z FAILED tests/x.py::t - oops\n"
                "plain info\n")
        lines = extract_error_lines(text)
        assert len(lines) == 2
        assert lines[0].startswith("##[error]")


class TestClustering:
    def test_cross_job_cluster(self):
        logs = {
            "tests": (DEMO / "job_tests.log").read_text(encoding="utf-8"),
            "lint": (DEMO / "job_lint.log").read_text(encoding="utf-8"),
        }
        clusters, events = cluster_logs(logs)
        assert events >= 6
        # the shared root cause clusters ACROSS jobs (retry count masked)
        conn = next(c for c in clusters if "ConnectionError" in c.template)
        assert conn.count == 2 and conn.jobs == {"tests", "lint"}
        exit_c = next(c for c in clusters
                      if "exit code" in c.template)
        assert exit_c.count == 2 and exit_c.jobs == {"tests", "lint"}
        # distinct failing tests stay distinct root causes
        failed = [c for c in clusters if c.template.startswith("FAILED")]
        assert len(failed) == 2

    def test_top_limit(self):
        logs = {"j": "\n".join(f"##[error]unique problem {i} code {i}{i}"
                               for i in range(30))}
        clusters, _ = cluster_logs(logs, top=5)
        assert len(clusters) == 1  # numbers masked → one template


class TestRuns:
    def test_parse_validates(self):
        with pytest.raises(ValueError):
            parse_runs("{not json")
        with pytest.raises(ValueError):
            parse_runs('[42]')
        runs = parse_runs('[{"name": "wf", "conclusion": "success"}]')
        assert runs[0]["workflow"] == "wf"

    def test_flaky_and_drift_on_demo(self):
        runs = parse_runs((DEMO / "runs.json").read_text(encoding="utf-8"))
        insight = analyze_runs(runs)
        assert insight.flaky == [{"workflow": "tests",
                                  "head_sha": "abc1234"}]
        assert insight.drift and insight.drift[0]["workflow"] == "lint"
        assert insight.drift[0]["factor"] >= 2
        wf = {w["workflow"]: w for w in insight.workflows}
        assert wf["tests"]["failures"] == 2

    def test_no_flaky_without_shared_sha(self):
        runs = parse_runs(json.dumps([
            {"workflow": "w", "conclusion": "success", "head_sha": "a" * 8},
            {"workflow": "w", "conclusion": "failure", "head_sha": "b" * 8},
        ]))
        assert analyze_runs(runs).flaky == []

    def test_drift_needs_history(self):
        runs = parse_runs(json.dumps([
            {"workflow": "w", "conclusion": "success", "head_sha": "a" * 8,
             "duration_s": d} for d in (10, 100)
        ]))
        assert analyze_runs(runs).drift == []


class TestReport:
    def test_markdown_bilingual(self):
        logs = {"tests": (DEMO / "job_tests.log").read_text(encoding="utf-8")}
        runs_text = (DEMO / "runs.json").read_text(encoding="utf-8")
        report = analyze(logs=logs, runs_text=runs_text)
        zh = render_markdown(report, "zh")
        en = render_markdown(report, "en")
        assert "CI 日志诊断" in zh and "Flaky" in zh and "时长漂移" in zh
        assert "CI Log Triage" in en and "Duration drift" in en


class TestCli:
    def test_logs_and_runs(self):
        r = CliRunner().invoke(cli, [
            "ciinspect", str(DEMO / "job_tests.log"),
            str(DEMO / "job_lint.log"),
            "--runs", str(DEMO / "runs.json")])
        assert r.exit_code == 0, r.output
        assert "根因聚类" in r.output and "abc1234" in r.output

    def test_fail_on_flaky(self):
        r = CliRunner().invoke(cli, [
            "ciinspect", "--runs", str(DEMO / "runs.json"),
            "--fail-on", "flaky"])
        assert r.exit_code == 1

    def test_json(self):
        r = CliRunner().invoke(cli, [
            "ciinspect", str(DEMO / "job_lint.log"), "-F", "json"])
        assert r.exit_code == 0, r.output
        payload = json.loads(r.output)
        assert payload["logs_analyzed"] == 1

    def test_requires_input(self):
        r = CliRunner().invoke(cli, ["ciinspect"])
        assert r.exit_code != 0

    def test_bad_runs_exit_2(self, tmp_path):
        bad = tmp_path / "runs.json"
        bad.write_text("{oops", encoding="utf-8")
        r = CliRunner().invoke(cli, ["ciinspect", "--runs", str(bad)])
        assert r.exit_code == 2


class TestApi:
    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from seatunnel_agent.ci_inspect.api import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_analyze_endpoint(self):
        resp = self._client().post("/api/ciinspect/analyze", json={
            "logs": [{"name": "tests",
                      "text": "##[error]boom at line 3\n##[error]boom at line 9"}],
            "lang": "en", "report": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["clusters"][0]["count"] == 2
        assert "CI Log Triage" in data["report"]

    def test_requires_input_400(self):
        resp = self._client().post("/api/ciinspect/analyze", json={})
        assert resp.status_code == 400

    def test_bad_runs_400(self):
        resp = self._client().post("/api/ciinspect/analyze",
                                   json={"runs_json": "{bad"})
        assert resp.status_code == 400

    def test_health(self):
        resp = self._client().get("/api/ciinspect/health")
        assert resp.json() == {"status": "ok", "agent": "ci_inspect"}
