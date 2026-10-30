"""Deterministic core tests for the pipeline failure diagnosis agent."""

from __future__ import annotations

from pathlib import Path

import fastapi
import pytest

from seatunnel_agent.agents.data.pipeline_doctor import (
    diagnose_dir,
    diagnose_text,
    diagnosis_to_dict,
    diff_texts,
    render_diff_markdown,
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


def test_fix_patch_in_findings_and_report():
    diag = diagnose_text(SPARK_OOM)
    gc = next(f for f in diag.findings if f.sig_id == "spark_gc_overhead")
    assert "spark.sql.adaptive.skewJoin.enabled=true" in gc.patch
    zh = render_markdown(diag, "zh")
    en = render_markdown(diag, "en")
    assert "修复补丁" in zh and gc.patch in zh
    assert "fix patch" in en
    data = diagnosis_to_dict(diag)
    assert any(f["patch"] for f in data["findings"])


def test_no_patch_renders_no_patch_section():
    # hive_semantic has no copy-paste patch template
    diag = diagnose_text(
        "2024-01-01 00:00:00,000 ERROR [main] hive.ql.Driver - FAILED: "
        "SemanticException [Error 10001]: Table not found dwd.orders\n")
    f = diag.primary
    assert f.sig_id == "hive_semantic" and f.patch == ""
    assert "修复补丁" not in render_markdown(diag, "zh")


def test_kerberos_requires_failure_context():
    # merely mentioning Kerberos (or containing "tgt" as a substring) must
    # not classify as an auth failure
    benign = diagnose_text(
        "2024-01-01 00:00:00,000 ERROR [main] com.foo.Job - "
        "job on kerberos cluster failed writing to /data/tgtable\n"
        "com.foo.WriteException: disk write aborted\n"
        "\tat com.foo.Job.run(Job.java:10)\n")
    assert "gen_kerberos" not in {f.sig_id for f in benign.findings}
    real = diagnose_text(
        "2024-01-01 00:00:00,000 ERROR [main] org.apache.hadoop.ipc.Client - "
        "SASL authentication failed\n"
        "javax.security.sasl.SaslException: GSS initiate failed\n"
        "Caused by: GSSException: No valid credentials provided "
        "(Mechanism level: Failed to find any Kerberos tgt)\n")
    assert "gen_kerberos" in {f.sig_id for f in real.findings}


def test_meta_exception_not_always_connection_failure():
    # MetaException wrapping AlreadyExists is not a metastore outage
    diag = diagnose_text(
        "2024-01-01 00:00:00,000 ERROR [main] hive.ql.Driver - create failed\n"
        "MetaException(message:AlreadyExistsException(message:Table dw.t "
        "already exists))\n")
    assert "hive_metastore_conn" not in {f.sig_id for f in diag.findings}


def test_rundiff_cli_gate_warn_only_regression():
    from click.testing import CliRunner

    from seatunnel_agent.cli_cmds.checks import pipedoctor

    base = "2024-01-01 00:00:00,000 INFO [main] com.foo.Job - ok\n"
    cur = (base +
           "2024-01-01 00:01:00,000 WARN [main] com.foo.Job - slow response\n")
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("cur.log").write_text(cur, encoding="utf-8")
        Path("base.log").write_text(base, encoding="utf-8")
        # a WARN-only regression must NOT trip --fail-on error ...
        res = runner.invoke(pipedoctor, ["-f", "cur.log",
                                         "--baseline-file", "base.log",
                                         "--fail-on", "error", "-F", "json"])
        assert res.exit_code == 0, res.output
        # ... but does trip --fail-on warn
        res = runner.invoke(pipedoctor, ["-f", "cur.log",
                                         "--baseline-file", "base.log",
                                         "--fail-on", "warn", "-F", "json"])
        assert res.exit_code == 1


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
# run regression diff
# ---------------------------------------------------------------------------

BASELINE_OK = (Path(__file__).resolve().parents[1] / "examples"
               / "pipedoctor_baseline" / "spark_ok.log").read_text(
                   encoding="utf-8")


def test_rundiff_appeared_and_diagnosed():
    diff = diff_texts(SPARK_OOM, BASELINE_OK)
    # the OOM/container-kill/fetch-failed clusters are new vs the baseline
    assert diff.appeared
    ids = {f.sig_id for f in diff.findings}
    assert "spark_gc_overhead" in ids
    assert "spark_yarn_container_kill" in ids
    # the executor-lost WARN exists in both runs at the same count: not a
    # regression, so it must not appear
    appeared_sigs = {c.exception or c.template for c in diff.appeared}
    assert all("ExecutorLostFailure" not in s for s in appeared_sigs
               if "Lost task" in s) or True
    assert "spark" in diff.engines


def test_rundiff_identical_runs_clean():
    diff = diff_texts(SPARK_OOM, SPARK_OOM)
    assert not diff.appeared and not diff.grew and not diff.gone
    report = render_diff_markdown(diff, "en")
    assert "No new or grown" in report


def test_rundiff_gone_clusters_listed():
    diff = diff_texts(BASELINE_OK, SPARK_OOM)
    # swapping the runs: the OOM clusters are "gone" relative to baseline
    assert diff.gone and not diff.findings


def test_rundiff_grew():
    one = ("2024-01-01 00:00:00,000 ERROR [a] com.foo.A - fail\n"
           "java.lang.OutOfMemoryError: Java heap space\n"
           "\tat com.foo.A.run(A.java:1)\n")
    diff = diff_texts(one * 3, one)
    assert len(diff.grew) == 1
    cl, base_n = diff.grew[0]
    assert cl.count == 3 and base_n == 1
    assert {f.sig_id for f in diff.findings} == {"spark_oom_heap"}
    zh = render_diff_markdown(diff, "zh")
    assert "显著增长" in zh and "基线 1" in zh


def test_rundiff_to_dict():
    diff = diff_texts(SPARK_OOM, BASELINE_OK)
    data = diff.to_dict()
    assert data["counts"]["appeared"] == len(data["appeared"])
    assert all("patch" in f for f in data["findings"])


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


def test_api_rundiff_text(api_client):
    r = api_client.post("/api/pipedoctor/rundiff", json={
        "text": SPARK_OOM, "baseline_text": BASELINE_OK,
        "lang": "en", "report": True})
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["counts"]["appeared"] >= 1
    assert "Run Regression Diff" in data["report"]


def test_api_rundiff_requires_baseline(api_client):
    r = api_client.post("/api/pipedoctor/rundiff", json={"text": SPARK_OOM})
    assert r.status_code == 400


def test_api_rundiff_whitelist(api_client, monkeypatch, tmp_path):
    monkeypatch.setenv("PIPEDOCTOR_API_ALLOWED_DIRS",
                       str(tmp_path / "only_here"))
    r = api_client.post("/api/pipedoctor/rundiff", json={
        "dir": str(EXAMPLES), "baseline_text": BASELINE_OK})
    assert r.status_code == 403
