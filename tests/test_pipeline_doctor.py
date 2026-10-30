"""Deterministic core tests for the pipeline failure diagnosis agent."""

from __future__ import annotations

from pathlib import Path

import fastapi
import pytest

from seatunnel_agent.agents.data.pipeline_doctor import (
    diagnose_dir,
    diagnose_text,
    diagnosis_to_dict,
    render_markdown,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "pipedoctor_demo"

SPARK_OOM = (EXAMPLES / "spark_oom.log").read_text(encoding="utf-8")
HIVE_META = (EXAMPLES / "hive_metastore.log").read_text(encoding="utf-8")
ST_PLUGIN = (EXAMPLES / "seatunnel_plugin.log").read_text(encoding="utf-8")


def _ids(diag) -> set[str]:
    return {f.sig_id for f in diag.findings}


def test_spark_oom_diagnosis():
    diag = diagnose_text(SPARK_OOM)
    assert "spark" in diag.engines
    ids = _ids(diag)
    assert "spark_gc_overhead" in ids
    assert "spark_yarn_container_kill" in ids
    assert "spark_fetch_failed" in ids
    # primary suspect is critical and the earliest critical finding
    assert diag.primary.severity == "critical"
    assert diag.primary.sig_id == "spark_gc_overhead"


def test_hive_metastore_diagnosis():
    diag = diagnose_text(HIVE_META)
    assert "hive" in diag.engines
    ids = _ids(diag)
    assert "hive_metastore_conn" in ids
    assert diag.primary.sig_id == "hive_metastore_conn"


def test_seatunnel_plugin_diagnosis():
    diag = diagnose_text(ST_PLUGIN)
    assert "seatunnel" in diag.engines
    ids = _ids(diag)
    assert "st_plugin_not_found" in ids
    assert "st_config_parse" in ids


def test_clean_log_is_healthy():
    diag = diagnose_text(
        "2024-01-01 00:00:00,000 INFO [main] com.foo.Job - started\n"
        "2024-01-01 00:00:01,000 INFO [main] com.foo.Job - done\n")
    assert not diag.findings and not diag.unmatched
    report = render_markdown(diag, "en")
    assert "healthy" in report


def test_unmatched_cluster_listed():
    diag = diagnose_text(
        "2024-01-01 00:00:00,000 ERROR [main] com.foo.Job - boom\n"
        "com.foo.TotallyCustomException: nothing in the kb matches this\n"
        "\tat com.foo.Job.run(Job.java:10)\n")
    assert not diag.findings
    assert len(diag.unmatched) == 1
    assert diag.unmatched[0].exception == "com.foo.TotallyCustomException"


def test_diagnose_dir_and_dict_roundtrip():
    diag = diagnose_dir(EXAMPLES)
    assert diag.files_scanned == 3
    data = diagnosis_to_dict(diag, top=5)
    # counts reflect the full diagnosis; the list is truncated to top
    assert data["counts"]["findings"] >= len(data["findings"])
    assert len(data["findings"]) <= 5
    assert {"spark", "hive", "seatunnel"} <= set(data["engines"])


def test_render_markdown_bilingual():
    diag = diagnose_text(SPARK_OOM)
    zh = render_markdown(diag, "zh")
    en = render_markdown(diag, "en")
    assert "首要嫌疑" in zh and "修复方案" in zh
    assert "Primary suspect" in en and "fix" in en
    assert "memoryOverhead" in en


def test_same_signature_clusters_merge():
    text = (
        "2024-01-01 00:00:00,000 ERROR [a] com.foo.A - fail\n"
        "java.lang.OutOfMemoryError: Java heap space\n"
        "\tat com.foo.A.run(A.java:1)\n"
        "2024-01-01 00:00:05,000 ERROR [b] com.bar.B - fail\n"
        "java.lang.OutOfMemoryError: Java heap space\n"
        "\tat com.bar.B.run(B.java:2)\n")
    diag = diagnose_text(text)
    oom = [f for f in diag.findings if f.sig_id == "spark_oom_heap"]
    assert len(oom) == 1 and oom[0].count == 2


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_client():
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.pipeline_doctor.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_diagnose_dir(api_client):
    r = api_client.post("/api/pipedoctor/diagnose", json={
        "dir": str(EXAMPLES), "lang": "en", "report": True})
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["counts"]["findings"] >= 5
    assert "Pipeline Failure Diagnosis" in data["report"]


def test_api_diagnose_text(api_client):
    r = api_client.post("/api/pipedoctor/diagnose", json={"text": SPARK_OOM})
    assert r.status_code == 200
    assert r.json()["result"]["counts"]["critical"] >= 2


def test_api_diagnose_outside_whitelist(api_client, monkeypatch, tmp_path):
    monkeypatch.setenv("PIPEDOCTOR_API_ALLOWED_DIRS",
                       str(tmp_path / "only_here"))
    r = api_client.post("/api/pipedoctor/diagnose",
                        json={"dir": str(EXAMPLES)})
    assert r.status_code == 403


def test_api_diagnose_requires_input(api_client):
    r = api_client.post("/api/pipedoctor/diagnose", json={})
    assert r.status_code == 400


def test_api_health(api_client):
    r = api_client.get("/api/pipedoctor/health")
    assert r.status_code == 200
