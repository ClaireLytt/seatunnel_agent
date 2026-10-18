"""In-process tests for the Config Migrate REST API (ticket 01).

Seam: the HTTP contract of /api/config_migrate/migrate — never the
internals of the rule-based migrator (those are covered by
tests/test_config_migrate.py).
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_DATAX_JOB = {
    "job": {
        "content": [{
            "reader": {
                "name": "mysqlreader",
                "parameter": {
                    "username": "root",
                    "password": "pw",
                    "connection": [{
                        "jdbcUrl": ["jdbc:mysql://localhost:3306/demo"],
                        "table": ["orders"],
                    }],
                    "column": ["id", "name"],
                },
            },
            "writer": {
                "name": "mysqlwriter",
                "parameter": {
                    "username": "root",
                    "password": "pw",
                    "connection": [{
                        "jdbcUrl": "jdbc:mysql://localhost:3306/demo2",
                        "table": ["orders_copy"],
                    }],
                    "column": ["id", "name"],
                },
            },
        }],
    },
}


@pytest.fixture()
def client() -> TestClient:
    from seatunnel_agent.agents.data.config_migrate.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_migrate_datax_success(client: TestClient) -> None:
    r = client.post("/api/config_migrate/migrate",
                    json={"text": json.dumps(_DATAX_JOB), "lang": "en"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["source_kind"] == "datax"
    assert "source {" in data["conf"] and "sink {" in data["conf"]
    assert "Jdbc" in data["conf"]
    # report is markdown rendered in the requested language
    assert "SeaTunnel Migration" in data["report"]


def test_migrate_report_lang_zh(client: TestClient) -> None:
    r = client.post("/api/config_migrate/migrate",
                    json={"text": json.dumps(_DATAX_JOB), "lang": "zh"})
    assert r.status_code == 200
    assert "迁移" in r.json()["report"]


def test_migrate_unknown_format(client: TestClient) -> None:
    r = client.post("/api/config_migrate/migrate",
                    json={"text": "SELECT 1 FROM dual", "lang": "en"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    assert data["conf"] == ""
    assert "Unrecognized file" in data["report"]


def test_migrate_empty_input_422(client: TestClient) -> None:
    r = client.post("/api/config_migrate/migrate",
                    json={"text": "   ", "lang": "en"})
    assert r.status_code == 422


# ── batch endpoint (ticket 02) ──

def test_batch_migrate_success(client: TestClient, tmp_path) -> None:
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / "a.json").write_text(json.dumps(_DATAX_JOB), encoding="utf-8")
    out = tmp_path / "out"
    r = client.post("/api/config_migrate/batch",
                    json={"jobs_dir": str(jobs), "out_dir": str(out),
                          "lang": "en"})
    assert r.status_code == 200
    data = r.json()
    assert data["stats"] == {"files": 1, "ok": 1, "failed": 0}
    assert (out / "a.conf").is_file()
    assert "`" in data["report"] and "a.json" in data["report"]


def test_batch_migrate_partial_failure(client: TestClient, tmp_path) -> None:
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / "good.json").write_text(json.dumps(_DATAX_JOB), encoding="utf-8")
    (jobs / "bad.json").write_text("{not valid json", encoding="utf-8")
    r = client.post("/api/config_migrate/batch",
                    json={"jobs_dir": str(jobs), "lang": "en"})
    assert r.status_code == 200
    data = r.json()
    assert data["stats"] == {"files": 2, "ok": 1, "failed": 1}
    assert "bad.json" in data["report"]


def test_batch_migrate_missing_dir_400(client: TestClient,
                                       tmp_path) -> None:
    bad = str(tmp_path / "nope")
    r = client.post("/api/config_migrate/batch",
                    json={"jobs_dir": bad, "lang": "en"})
    assert r.status_code == 400
    assert r.json()["detail"] == {"code": "bad_dir", "path": bad}


def test_batch_migrate_blank_dir_422(client: TestClient) -> None:
    r = client.post("/api/config_migrate/batch",
                    json={"jobs_dir": "   ", "lang": "en"})
    assert r.status_code == 422
