"""UI testing agent REST API — seams agreed in the batch-5b review:

  GET  /api/uitest/runs            history list from runs/<ts>/result.json
  GET  /api/uitest/meta            suite / agent-picker choices
  POST /api/uitest/case            YAML validate & save (422 on bad input)
  GET  /api/uitest/report/{id}     404 unknown run, 422 bad id
  POST /api/uitest/run             SSE protocol (run_suite monkeypatched)
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from seatunnel_agent.agents.devops.ui_testing import runner
from seatunnel_agent.agents.devops.ui_testing.api import router


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _seed_run(runs_dir, run_id: str, verdicts: list[str], *,
              suite: str = "smoke", report: bool = True) -> None:
    d = runs_dir / run_id
    d.mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({
        "started_at": run_id,
        "suite": suite,
        "elapsed_ms": 1234,
        "tokens": 0,
        "cases": [{"case_id": f"C{i}", "verdict": v}
                  for i, v in enumerate(verdicts)],
    }), encoding="utf-8")
    if report:
        (d / "report.html").write_text("<html></html>", encoding="utf-8")


def test_meta_lists_suites_and_agents(client):
    r = client.get("/api/uitest/meta")
    assert r.status_code == 200
    data = r.json()
    assert "smoke" in data["suites"]
    keys = [a["key"] for a in data["agents"]]
    assert keys[0] == "all"
    # datacompare retired from the YAML engine (ticket 11): its coverage
    # lives in tests/test_datacompare_page.py / test_datacompare_api.py
    assert "datacompare" not in keys
    assert "dataskew" in keys
    zh = {a["key"]: a["label_zh"] for a in data["agents"]}
    assert zh["dataskew"] == "数据倾斜分析"


def test_case_save_rejects_bad_yaml(client):
    assert client.post("/api/uitest/case", json={"text": ""}).status_code == 422
    assert client.post("/api/uitest/case",
                       json={"text": "bad: ["}).status_code == 422


def test_case_save_writes_user_case(client, tmp_path, monkeypatch):
    from seatunnel_agent.agents.devops.ui_testing import loader
    monkeypatch.setattr(loader, "USER_CASES_DIR", tmp_path / "cases")
    yaml_text = (
        "- id: ZZ9\n"
        "  title: saved via api\n"
        "  tags: [full, sqlite]\n"
        "  page: /dataskew\n"
        "  steps:\n"
        "    - ai: click compare\n"
        "  expect:\n"
        "    - ai_judge: a result table\n")
    r = client.post("/api/uitest/case", json={"text": yaml_text})
    assert r.status_code == 200
    assert r.json()["ids"] == ["ZZ9"]
    assert (tmp_path / "cases" / "zz9.yaml").read_text(
        encoding="utf-8") == yaml_text


def test_report_bad_id_and_missing(client, tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    assert client.get("/api/uitest/report/../etc").status_code in (404, 422)
    assert client.get("/api/uitest/report/notanid").status_code == 422
    assert client.get("/api/uitest/report/20260101_000001").status_code == 404
    _seed_run(tmp_path, "20260101_000001", ["PASS"])
    assert client.get("/api/uitest/report/20260101_000001").status_code == 200


def test_run_streams_progress_then_done(client, monkeypatch, tmp_path):
    """SSE protocol: progress events, then done with counts + run id."""
    from types import SimpleNamespace

    from seatunnel_agent.agents.devops.ui_testing import report

    def fake_run_suite(suite, case_ids=None, no_llm=True, on_progress=None,
                       **kw):
        cr = SimpleNamespace(verdict="PASS", case_id="F1",
                             title="fake", elapsed_ms=10)
        on_progress(1, 1, cr)
        rr = SimpleNamespace(
            counts=lambda: {"PASS": 1, "FAIL": 0, "ERROR": 0,
                            "SKIP": 0, "MANUAL": 0, "HEALED": 0},
            elapsed_ms=10)
        run_dir = tmp_path / "20260101_000009"
        run_dir.mkdir()
        return rr, run_dir

    monkeypatch.setattr(runner, "run_suite", fake_run_suite)
    for fn in ("write_json", "write_html", "write_labels_patch"):
        monkeypatch.setattr(report, fn, lambda *a, **k: None)

    events = []
    with client.stream("POST", "/api/uitest/run",
                       json={"suite": "smoke", "agent": "all",
                             "case_ids": "", "no_llm": True}) as r:
        assert r.status_code == 200
        for line in r.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

    assert [e["type"] for e in events] == ["progress", "done"]
    assert "F1" in events[0]["line"]
    done = events[1]
    assert done["run_id"] == "20260101_000009"
    assert done["counts"]["PASS"] == 1


def test_run_rejects_unknown_suite(client):
    r = client.post("/api/uitest/run",
                    json={"suite": "nope", "agent": "all",
                          "case_ids": "", "no_llm": True})
    assert r.status_code == 422


def test_runs_lists_history_newest_first(client, tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    _seed_run(tmp_path, "20260101_000001", ["PASS", "FAIL"])
    _seed_run(tmp_path, "20260102_000002", ["PASS"], suite="full",
              report=False)
    # a dir without result.json (crashed run) must be skipped, not 500
    (tmp_path / "20260103_000003").mkdir()

    r = client.get("/api/uitest/runs")
    assert r.status_code == 200
    runs = r.json()["runs"]
    assert [x["run_id"] for x in runs] == ["20260102_000002",
                                           "20260101_000001"]
    newest, oldest = runs
    assert newest["suite"] == "full"
    assert newest["has_report"] is False
    assert oldest["has_report"] is True
    assert oldest["elapsed_ms"] == 1234
    assert oldest["counts"]["PASS"] == 1
    assert oldest["counts"]["FAIL"] == 1
