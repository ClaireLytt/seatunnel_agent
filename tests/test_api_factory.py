"""Unit tests for seatunnel_agent.common.api_factory.make_agent_router."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_agent_router

# ---- fake domain layer ---------------------------------------------------- #

@dataclass
class _FakeReport:
    items: list[str]


def _fake_domain(path: str, *, dialect: str = "ansi") -> _FakeReport:
    return _FakeReport(items=[f"{path}:{dialect}"])


def _fake_report_to_dict(report: _FakeReport, lang: str) -> dict[str, Any]:
    return {"items": report.items, "lang": lang}


def _fake_render_markdown(report: _FakeReport, lang: str) -> str:
    return f"# {lang}\n" + "\n".join(report.items)


def _failing_domain(path: str, *, dialect: str = "ansi") -> _FakeReport:
    raise ValueError("parse boom")


class _Req(BaseModel):
    sql_dir: str = Field(..., min_length=1)
    dialect: str = "ansi"
    lang: str = "zh"
    report: bool = False


# ---- fixtures -------------------------------------------------------------- #

@pytest.fixture()
def _tmp_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_ALLOWED_DIRS", str(tmp_path))
    return tmp_path


def _make_client(domain_fn=_fake_domain) -> TestClient:
    router = make_agent_router(
        prefix="/api/test",
        tags=["test"],
        domain_fn=domain_fn,
        request_model=_Req,
        allowed_dirs_env="TEST_ALLOWED_DIRS",
        health_name="test_agent",
        report_to_dict=_fake_report_to_dict,
        render_markdown=_fake_render_markdown,
    )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---- tests ----------------------------------------------------------------- #

class TestMakeAgentRouter:
    def test_success(self, _tmp_dir):
        client = _make_client()
        resp = client.post("/api/test/check", json={
            "sql_dir": str(_tmp_dir), "dialect": "hive",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"]["lang"] == "zh"
        assert str(_tmp_dir) in body["result"]["items"][0]
        assert body["report"] is None
        assert body["elapsed_ms"] >= 0

    def test_success_with_report(self, _tmp_dir):
        client = _make_client()
        resp = client.post("/api/test/check", json={
            "sql_dir": str(_tmp_dir), "report": True,
        })
        assert resp.status_code == 200
        assert resp.json()["report"].startswith("# zh")

    def test_forbidden_path(self, _tmp_dir):
        client = _make_client()
        resp = client.post("/api/test/check", json={
            "sql_dir": "/some/forbidden/path",
        })
        assert resp.status_code == 403

    def test_domain_error(self, _tmp_dir):
        client = _make_client(domain_fn=_failing_domain)
        resp = client.post("/api/test/check", json={
            "sql_dir": str(_tmp_dir),
        })
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["code"] == "check_failed"
        assert "parse boom" in detail["error"]

    def test_health(self, _tmp_dir):
        client = _make_client()
        resp = client.get("/api/test/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "agent": "test_agent"}
