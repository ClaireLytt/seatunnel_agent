# -*- coding: utf-8 -*-
"""Tests for the batch log inspection agent (log_inspect).

Deterministic only — no LLM, no database, no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.log_inspect import (
    collect_log_files,
    render_markdown,
    report_to_dict,
    scan_dir,
    scan_text,
)
from seatunnel_agent.log_inspect.clusterer import (
    cluster_events,
    extract_events,
    normalize_message,
)

runner = CliRunner()

DEMO_DIR = Path(__file__).resolve().parents[1] / "examples" / "logs_demo"

TRACE = """\
2024-03-01 08:00:05,882 ERROR [task-1] org.apache.foo.JdbcSource - Connect failed
java.sql.SQLNonTransientConnectionException: Could not connect to address=(host=10.1.2.3)(port=3306): Connection refused
\tat org.mariadb.jdbc.internal.util.exceptions.ExceptionFactory.createException(ExceptionFactory.java:73)
\tat org.apache.foo.JdbcSourceReader.open(JdbcSourceReader.java:88)
Caused by: java.net.ConnectException: Connection refused: connect
\tat java.base/sun.nio.ch.Net.pollConnect(Native Method)
\t... 12 more
2024-03-01 08:00:07,001 INFO  [main] org.apache.foo.Engine - continuing
"""


# ─────────────────────────── normalization ───────────────────────────

@pytest.mark.parametrize("raw,expect", [
    ("txn 44121 took 30841 ms", "txn <N> took <N> ms"),
    ("read /tmp/data/part-0001.orc failed", "read <PATH> failed"),
    ("connect to 10.1.2.3:3306 refused", "connect to <ADDR> refused"),
    ("task 0x7fa3bc crashed", "task <HEX> crashed"),
    ("at 2024-03-01 08:00:05 boom", "at <TS> boom"),
])
def test_normalize_message(raw, expect):
    assert normalize_message(raw) == expect


# ─────────────────────────── event extraction ───────────────────────────

def test_extract_trace_as_single_event_with_root_cause():
    events, n_lines = extract_events(TRACE)
    assert n_lines == 8
    assert len(events) == 1
    ev = events[0]
    assert ev.level == "error"
    assert ev.timestamp.startswith("2024-03-01 08:00:05")
    # root cause = the last Caused by, not the outer wrapper
    assert ev.exception == "java.net.ConnectException"
    assert ev.top_frame == "java.base/sun.nio.ch.Net.pollConnect"
    assert "SQLNonTransientConnectionException" in ev.raw


def test_extract_strips_thread_and_logger_prefix():
    events, _ = extract_events(
        "2024-03-01 08:00:07,001 WARN  [task-2] com.foo.Bar - Task backoff, "
        "retry 1/3 in 5000 ms")
    (ev,) = events
    assert ev.level == "warn"
    assert ev.message.startswith("Task backoff")


def test_extract_bare_trace_without_level_line():
    events, _ = extract_events(
        "java.lang.IllegalStateException: boom\n"
        "\tat com.foo.Bar.baz(Bar.java:10)\n")
    (ev,) = events
    assert ev.level == "error"
    assert ev.exception == "java.lang.IllegalStateException"
    assert ev.top_frame == "com.foo.Bar.baz"


def test_extract_ignores_info_and_respects_include_warn():
    text = ("2024-01-01 00:00:00 INFO ok\n"
            "2024-01-01 00:00:01 WARN w1\n"
            "2024-01-01 00:00:02 ERROR e1\n")
    both, _ = extract_events(text)
    assert [e.level for e in both] == ["warn", "error"]
    errors_only, _ = extract_events(text, include_warn=False)
    assert [e.level for e in errors_only] == ["error"]


def test_skipped_warn_trace_is_not_a_phantom_error():
    # errors-only mode must swallow the WARN's own stack trace instead of
    # re-detecting it as a bare-trace ERROR event
    text = ("2024-01-01 00:00:01 WARN [t] com.foo.Bar - retry failed\n"
            "java.io.UncheckedIOException: wrapper\n"
            "\tat com.foo.Bar.baz(Bar.java:10)\n"
            "Caused by: java.net.SocketTimeoutException: timeout\n"
            "\tat com.foo.Net.read(Net.java:5)\n")
    events, _ = extract_events(text, include_warn=False)
    assert events == []
    with_warn, _ = extract_events(text)
    assert [e.level for e in with_warn] == ["warn"]
    assert with_warn[0].exception == "java.net.SocketTimeoutException"


def test_info_line_mentioning_error_is_not_an_event():
    events, _ = extract_events(
        "2024-01-01 00:00:00 INFO Task state changed from RUNNING to ERROR\n")
    assert events == []


def test_oversized_file_truncation_warns(tmp_path, monkeypatch):
    from seatunnel_agent.log_inspect import clusterer

    monkeypatch.setattr(clusterer, "MAX_FILE_BYTES", 100)
    log = tmp_path / "big.log"
    log.write_text("2024-01-01 00:00:00 ERROR boom\n" * 50, encoding="utf-8")
    report = clusterer.scan_files([log])
    assert any("上限" in w for w in report.warnings)


# ─────────────────────────── clustering ───────────────────────────

def test_cluster_same_root_cause_across_files():
    ev1, _ = extract_events(TRACE, file_label="a.log")
    ev2, _ = extract_events(TRACE.replace("10.1.2.3", "10.9.8.7"),
                            file_label="b.log")
    clusters = cluster_events(ev1 + ev2)
    assert len(clusters) == 1
    c = clusters[0]
    assert c.count == 2
    assert c.files == {"a.log": 1, "b.log": 1}
    assert c.first_ts and c.last_ts


def test_cluster_ordering_errors_first_then_count():
    text = ("2024-01-01 00:00:01 WARN slow 1\n" * 5
            + "2024-01-01 00:00:02 ERROR boom 1\n")
    events, _ = extract_events(text)
    clusters = cluster_events(events)
    assert clusters[0].level == "error"


# ─────────────────────────── directory scan ───────────────────────────

def test_collect_log_files_demo():
    files = collect_log_files(DEMO_DIR)
    assert len(files) == 3


def test_scan_demo_dir():
    report = scan_dir(DEMO_DIR)
    c = report.counts()
    assert report.files_scanned == 3
    assert c["error"] == 3           # ConnectException / OOM / ClassNotFound
    assert c["warn"] == 3
    top = report.clusters[0]
    assert top.exception == "java.net.ConnectException"
    assert top.count == 3
    assert len(top.files) == 2


def test_scan_missing_dir_returns_warning(tmp_path):
    report = scan_dir(tmp_path)
    assert not report.clusters
    assert report.warnings


def test_scan_text_inline():
    report = scan_text(TRACE)
    assert report.events == 1
    assert report.clusters[0].exception == "java.net.ConnectException"


# ─────────────────────────── rendering ───────────────────────────

def test_render_markdown_zh_and_en():
    report = scan_dir(DEMO_DIR)
    zh = render_markdown(report, "zh")
    en = render_markdown(report, "en")
    assert "批量日志巡检" in zh and "Top 异常簇" in zh
    assert "Batch Log Inspection" in en and "Top clusters" in en


def test_render_markdown_clean():
    report = scan_text("2024-01-01 00:00:00 INFO all good\n")
    assert "干净" in render_markdown(report, "zh")


def test_render_respects_top_limit():
    text = "".join(f"2024-01-01 00:00:00 ERROR boom type{i} x\n"
                   for i in range(8))
    report = scan_text(text)
    md = render_markdown(report, "zh", top=3)
    assert md.count("### ⛔ 簇") == 3


def test_report_to_dict_is_json_serializable():
    data = report_to_dict(scan_dir(DEMO_DIR), top=5)
    assert len(data["clusters"]) <= 5
    json.dumps(data)


# ─────────────────────────── CLI ───────────────────────────

def test_cli_loginspect_dir():
    r = runner.invoke(cli, ["loginspect", "--dir", str(DEMO_DIR)])
    assert r.exit_code == 0, r.output
    assert "批量日志巡检" in r.output


def test_cli_loginspect_requires_source():
    r = runner.invoke(cli, ["loginspect"])
    assert r.exit_code != 0


def test_cli_loginspect_json_and_fail_on(tmp_path):
    out = tmp_path / "report.json"
    r = runner.invoke(cli, ["loginspect", "--dir", str(DEMO_DIR),
                            "-F", "json", "--fail-on", "error",
                            "-o", str(out)])
    assert r.exit_code == 1          # demo logs carry error clusters
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["counts"]["error"] >= 1


def test_cli_loginspect_single_file_no_warn(tmp_path):
    log = tmp_path / "x.log"
    log.write_text("2024-01-01 00:00:01 WARN only warnings here\n",
                   encoding="utf-8")
    r = runner.invoke(cli, ["loginspect", "--file", str(log), "--no-warn",
                            "--fail-on", "error"])
    assert r.exit_code == 0, r.output


# ─────────────────────────── REST API ───────────────────────────

@pytest.fixture()
def api_client():
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.log_inspect.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_scan_dir(api_client):
    r = api_client.post("/api/loginspect/scan", json={
        "dir": str(DEMO_DIR), "lang": "en", "report": True})
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["counts"]["error"] == 3
    assert "Batch Log Inspection" in data["report"]


def test_api_scan_text(api_client):
    r = api_client.post("/api/loginspect/scan", json={"text": TRACE})
    assert r.status_code == 200
    assert r.json()["result"]["counts"]["events"] == 1


def test_api_scan_dir_outside_whitelist(api_client, monkeypatch, tmp_path):
    monkeypatch.setenv("LOGINSPECT_API_ALLOWED_DIRS",
                       str(tmp_path / "only_here"))
    r = api_client.post("/api/loginspect/scan", json={"dir": str(DEMO_DIR)})
    assert r.status_code == 403


def test_api_scan_requires_input(api_client):
    r = api_client.post("/api/loginspect/scan", json={})
    assert r.status_code == 400
    assert api_client.get("/api/loginspect/health").json()["status"] == "ok"
