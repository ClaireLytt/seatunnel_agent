"""Browser tests for the React /dataskew page (ticket 04).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_transpile_page.py. Deselected by default (needs a browser +
built dist):

    pytest -m uitest tests/test_dataskew_page.py

Equivalence coverage for the retired uitest YAML cases (cases/dataskew.yaml
DSK1-DSK21, scroll SCR9, fixture connect_skew_sqlite — removed in this
ticket): static rule findings (DSK2/DSK5), clean SQL (DSK7), clear (DSK8),
English report (DSK10), verify without connection (DSK11/DSK19), SQLite
connect + live probe (DSK12/DSK13), consistency without optimized SQL
(DSK14), history refresh+load (DSK16), file upload (DSK18), plus the
sql_review localStorage bridge pickup. DSKA1 (real LLM) stays manual; the
LLM path is covered deterministically by the llm_unavailable fallback at
the API layer (tests/test_dataskew_session_api.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import assert_dialect_switch, labeled_select, make_page_url
from tests.conftest import download_text as _download_text
from tests.conftest import zh_page as _zh_page

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.data_skew.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
_DEMO_DB = ""  # set by the page_url fixture (seeded per-test)

DISTINCT_SQL = "SELECT COUNT(DISTINCT user_id) FROM ods.user_log"
GROUP_SQL = "SELECT status, COUNT(*) FROM dc_test_orders_a GROUP BY status"


def _seed_demo_db(monkeypatch, tmp_path):
    """Seeded SQLite demo db (the repo copy is gitignored; CI builds it)."""
    from seatunnel_agent.agents.devops.ui_testing.seed_sqlite import seed_sqlite

    global _DEMO_DB
    _DEMO_DB = str(seed_sqlite(tmp_path / "uitest_demo.db"))


page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.data_skew.api:router", "/dataskew",
    env={"SEATUNNEL_SKEW_HISTORY_PATH": "{tmp}/history.jsonl"},
    post_setup=_seed_demo_db)


def _connect_sqlite(page):
    """Fixture-equivalent of the retired connect_skew_sqlite YAML steps."""
    from playwright.sync_api import expect

    page.locator("summary", has_text="Connect data source").click()
    labeled_select(page, "Datasource type").select_option("sqlite")
    page.get_by_text("Database").locator("xpath=following-sibling::input").fill(
        _DEMO_DB)
    page.get_by_role("button", name="Connect", exact=True).click()
    expect(page.get_by_text("Connected", exact=False)).to_be_visible(
        timeout=10000)


@pytest.mark.uitest
def test_dataskew_page_smoke(page_url):
    """Page loads: heading, selects, all four accordions; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="SQL Data Skew Analyzer")).to_be_visible()
        expect(page.locator("#dsk-sql-box")).to_be_visible()
        expect(page.get_by_role("button", name="Analyze Skew",
                                exact=True)).to_be_disabled()  # empty SQL
        for acc in ("Connect data source", "SeaTunnel split-key check",
                    "Skew drift", "Runtime diagnosis", "Analysis history"):
            expect(page.locator("summary", has_text=acc)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_dataskew_static_distinct_finding_zh(page_url):
    """DSK2: COUNT(DISTINCT) single-point aggregation flagged (zh report)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.locator("#dsk-sql-box").fill(DISTINCT_SQL)
        page.get_by_role("button", name="开始分析", exact=True).click()

        report = page.locator(".dsk-report-card")
        expect(report).to_be_visible(timeout=10000)
        expect(report).to_contain_text("COUNT(DISTINCT)")
        expect(report).to_contain_text("下载报告")
        browser.close()


@pytest.mark.uitest
def test_dataskew_clean_sql_no_optimized(page_url):
    """DSK7/DSK10: clean SQL yields an English report, no optimized-SQL
    download, no traceback."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill("SELECT id FROM t WHERE id = 1")
        page.get_by_role("button", name="Analyze Skew", exact=True).click()

        report = page.locator(".dsk-report-card")
        expect(report).to_be_visible(timeout=10000)
        expect(page.get_by_role("button", name="Download Report (.md)",
                                exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="Download Optimized SQL (.sql)",
                                exact=True)).to_have_count(0)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_dataskew_clear_resets(page_url):
    """DSK8: Clear empties the editor and restores the placeholder."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill(DISTINCT_SQL)
        page.get_by_role("button", name="Analyze Skew", exact=True).click()
        expect(page.locator(".dsk-report-card")).to_be_visible(timeout=10000)

        page.get_by_role("button", name="Clear", exact=True).click()
        expect(page.locator("#dsk-sql-box")).to_have_value("")
        expect(page.get_by_text(
            "The skew analysis report will appear here")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_dataskew_verify_needs_connection(page_url):
    """DSK11/DSK19: Verify without a connection shows the localized hint."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill(GROUP_SQL)
        page.locator("summary", has_text="Connect data source").click()
        page.get_by_role("button", name="Verify Skew (live data)",
                         exact=True).click()
        expect(page.get_by_text("Connect a data source first",
                                exact=False)).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_dataskew_sqlite_connect_and_probe(page_url):
    """DSK12/DSK13: SQLite connect, then a live probe appends the measured
    section to the report."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill(GROUP_SQL)
        page.get_by_role("button", name="Analyze Skew", exact=True).click()
        expect(page.locator(".dsk-report-card")).to_be_visible(timeout=10000)

        _connect_sqlite(page)
        page.get_by_role("button", name="Verify Skew (live data)",
                         exact=True).click()
        expect(page.locator(".dsk-report-card")).to_contain_text(
            "Skew Verification", timeout=15000)
        browser.close()


@pytest.mark.uitest
def test_dataskew_consistency_needs_optimized(page_url):
    """DSK14: consistency without an optimized SQL shows the hint."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill(GROUP_SQL)
        _connect_sqlite(page)
        page.get_by_role("button",
                         name="Measure Consistency (runs both SQLs)",
                         exact=True).click()
        expect(page.get_by_text("Generate the optimized SQL first",
                                exact=False)).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_dataskew_splitkey_needs_conf(page_url):
    """Split-key check with an empty config shows the localized hint."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        _connect_sqlite(page)
        page.locator("summary", has_text="SeaTunnel split-key check").click()
        page.get_by_role("button", name="Check split key", exact=True).click()
        expect(page.get_by_text("Paste a SeaTunnel job config first",
                                exact=False)).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_dataskew_history_refresh_and_load(page_url):
    """DSK16: history refresh lists the run; load refills the editor."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill(DISTINCT_SQL)
        page.get_by_role("button", name="Analyze Skew", exact=True).click()
        expect(page.locator(".dsk-report-card")).to_be_visible(timeout=10000)

        page.locator("summary", has_text="Analysis history").click()
        page.get_by_role("button", name="Refresh", exact=True).click()
        hist_table = page.locator("aside table")  # report tables live in main
        expect(hist_table).to_be_visible()
        expect(hist_table).to_contain_text("COUNT(DISTINCT")

        page.get_by_role("button", name="Clear", exact=True).click()
        expect(page.locator("#dsk-sql-box")).to_have_value("")
        page.get_by_role("button", name="Load selected", exact=True).click()
        expect(page.locator("#dsk-sql-box")).to_have_value(DISTINCT_SQL)
        browser.close()


@pytest.mark.uitest
def test_dataskew_upload_fills_editor(page_url, tmp_path):
    """DSK18: uploading a .sql file fills the editor."""
    from playwright.sync_api import expect, sync_playwright

    sql_file = tmp_path / "upload_demo.sql"
    sql_file.write_text(DISTINCT_SQL, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator('input[type="file"]').first.set_input_files(str(sql_file))
        expect(page.locator("#dsk-sql-box")).to_have_value(DISTINCT_SQL)
        browser.close()


@pytest.mark.uitest
def test_dataskew_bridge_pickup(page_url):
    """SQL handed over from sql_review via localStorage prefills the box."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="commit")
        page.evaluate("localStorage.setItem('st_dataskew_sql', 'SELECT 42')")
        page.goto(page_url, wait_until="networkidle")

        expect(page.locator("#dsk-sql-box")).to_have_value("SELECT 42")
        assert page.evaluate(
            "localStorage.getItem('st_dataskew_sql')") is None
        browser.close()


@pytest.mark.uitest
def test_dataskew_conn_cookie_handoff(page_url):
    """st_dataskew_conn cookie pre-fills the connection form (no password)
    and opens the accordion."""
    import json
    from urllib.parse import quote, urlparse

    from playwright.sync_api import expect, sync_playwright

    host = urlparse(page_url).hostname
    cookie = quote(json.dumps({
        "ds_type": "mysql", "host": "db-b", "port": 3306,
        "database": "shop", "username": "ro"}))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        ctx.add_cookies([{"name": "st_dataskew_conn", "value": cookie,
                          "domain": host, "path": "/"}])
        page = ctx.new_page()
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_text("Connection handed over",
                                exact=False)).to_be_visible()
        expect(page.get_by_text("Host").locator(
            "xpath=following-sibling::input")).to_have_value("db-b")
        browser.close()


STUB_OPTIMIZED_SQL = ("SELECT user_id, SUM(cnt) FROM ("
                      "SELECT user_id, COUNT(*) AS cnt FROM ods.user_log "
                      "GROUP BY user_id, bucket) t GROUP BY user_id")


@pytest.fixture()
def stub_llm(monkeypatch):
    """Deterministic (zero-token) LLM mode: stub the agent + settings at
    their source modules so /api/skew/analyze mode=llm returns an optimized
    SQL without calling a model. Reusable pattern for LLM-gated controls."""
    from seatunnel_agent.agents.data.data_skew import agent as agent_mod
    from seatunnel_agent.agents.data.data_skew.agent import SkewAnalysisResult
    from seatunnel_agent.agents.data.data_skew.report import SkewReport
    from seatunnel_agent.common import config as config_mod

    class _StubAgent:
        def __init__(self, *args, **kwargs):
            pass

        def analyze(self, sql, use_llm=True, probe_context=""):
            rep = SkewReport(optimized_sql=STUB_OPTIMIZED_SQL)
            return SkewAnalysisResult(
                report=rep, used_llm=True,
                markdown="## Stub Report\n\nGROUP BY hotspot rewritten.")

    monkeypatch.setattr(agent_mod, "DataSkewAgent", _StubAgent)
    monkeypatch.setattr(config_mod, "load_settings", lambda *a, **kw: object())


def _analyze_llm(page):
    """Run an analysis in (stubbed) LLM mode so the optimized-SQL card with
    its download + Copy buttons renders."""
    from playwright.sync_api import expect

    page.locator("#dsk-sql-box").fill(GROUP_SQL)
    labeled_select(page, "Analysis Mode").select_option("llm")
    page.get_by_role("button", name="Analyze Skew", exact=True).click()
    expect(page.locator(".dsk-report-card")).to_be_visible(timeout=10000)


@pytest.mark.uitest
def test_dataskew_download_report(page_url):
    """Ticket 01: Download Report really downloads — suggested_filename is
    data_skew_report.md and the content is the non-empty report."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill(DISTINCT_SQL)
        page.get_by_role("button", name="Analyze Skew", exact=True).click()
        expect(page.locator(".dsk-report-card")).to_be_visible(timeout=10000)

        with page.expect_download() as dl:
            page.get_by_role("button", name="Download Report (.md)",
                             exact=True).click()
        report = dl.value
        assert report.suggested_filename == "data_skew_report.md"
        report_text = _download_text(report)
        assert report_text.strip()
        assert "COUNT(DISTINCT" in report_text
        browser.close()


@pytest.mark.uitest
def test_dataskew_download_optimized_sql(page_url, stub_llm):
    """Ticket 01: Download Optimized SQL really downloads —
    my_task_optimized.sql with the optimized SQL as content."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        _analyze_llm(page)
        with page.expect_download() as dl:
            page.get_by_role("button", name="Download Optimized SQL (.sql)",
                             exact=True).click()
        sql_dl = dl.value
        assert sql_dl.suggested_filename == "my_task_optimized.sql"
        assert _download_text(sql_dl).strip() == STUB_OPTIMIZED_SQL
        browser.close()


@pytest.mark.uitest
def test_dataskew_copy_sql_clipboard(page_url, stub_llm):
    """Ticket 01: Copy writes the optimized SQL to the clipboard
    (clipboard-read/clipboard-write context permissions + readText)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            permissions=["clipboard-read", "clipboard-write"])
        page = ctx.new_page()
        page.goto(page_url, wait_until="networkidle")

        _analyze_llm(page)
        page.get_by_role("button", name="Copy", exact=True).click()
        expect(page.get_by_text("Copied", exact=False)).to_be_visible()

        clipboard = page.evaluate("() => navigator.clipboard.readText()")
        assert clipboard == STUB_OPTIMIZED_SQL
        browser.close()


# ─────────────────── ticket 04: panel-control coverage ───────────────────

# Single-source SeaTunnel job config against the seeded SQLite demo table:
# the configured split key `qty` holds only 5 distinct values (low_ndv for
# 2 tasks), so the measured check recommends `id` and returns a patched conf.
SPLITKEY_CONF = """\
env { parallelism = 2 }
source {
  Jdbc {
    url = "jdbc:sqlite:demo.db"
    table_path = "dc_test_metrics_a"
    partition_column = "qty"
    partition_num = 2
  }
}
sink { Console {} }
"""


def _write_eventlog(path: Path) -> None:
    """Minimal Spark event log: stage 1 has a 60s straggler vs a 2s median
    (confirmed skew), stage 2 is even (same shape as tests/test_data_skew.py)."""
    import json

    events: list[dict] = [
        {"Event": "SparkListenerApplicationStart", "App Name": "pw_app"},
        {"Event": "SparkListenerStageCompleted",
         "Stage Info": {"Stage ID": 1, "Stage Name": "Exchange"}},
        {"Event": "SparkListenerStageCompleted",
         "Stage Info": {"Stage ID": 2, "Stage Name": "Scan"}},
    ]
    for sid, durs in ((1, (2000, 2000, 2500, 60_000)),
                      (2, (3000, 3100, 2900, 3000))):
        for d in durs:
            events.append({
                "Event": "SparkListenerTaskEnd", "Stage ID": sid,
                "Task Info": {"Launch Time": 0, "Finish Time": d},
                "Task Metrics": {"Shuffle Read Metrics": {
                    "Remote Bytes Read": 0, "Local Bytes Read": 0}}})
    path.write_text("\n".join(json.dumps(e) for e in events),
                    encoding="utf-8")


@pytest.fixture()
def no_llm_key(monkeypatch):
    """Deterministic no-API-key environment: load_settings raises, so
    mode=llm degrades to the static scan with the banner (never a model
    call)."""
    from seatunnel_agent.common import config as config_mod

    def _raise(*args, **kwargs):
        raise RuntimeError("no api key configured (test)")

    monkeypatch.setattr(config_mod, "load_settings", _raise)


@pytest.fixture()
def stub_presets(monkeypatch):
    """One saved SQLite connection preset, served from a stub store (the
    real store reads ~/.seatunnel-agent — not touched here)."""
    from seatunnel_agent.agents.data.data_comparison import (
        presets as presets_mod,
    )

    class _Store:
        def __init__(self, *args, **kwargs):
            pass

        def list(self):
            return [{"name": "pw_demo", "ds_type": "sqlite"}]

        def get_by_name(self, name):
            if name != "pw_demo":
                return None
            return {"name": "pw_demo", "ds_type": "sqlite", "host": "",
                    "port": "", "database": _DEMO_DB, "username": "",
                    "password": ""}

    monkeypatch.setattr(presets_mod, "ConnectionPresetsStore", _Store)


@pytest.mark.uitest
def test_dataskew_llm_mode_no_key_banner(page_url, no_llm_key):
    """Mode select switched to llm without an API key: the analysis
    degrades deterministically to static with the localized banner."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill(DISTINCT_SQL)
        labeled_select(page, "Analysis Mode").select_option("llm")
        page.get_by_role("button", name="Analyze Skew", exact=True).click()

        report = page.locator(".dsk-report-card")
        expect(report).to_be_visible(timeout=10000)
        expect(report).to_contain_text("LLM is not configured")
        expect(report).to_contain_text("COUNT(DISTINCT)")  # static findings
        browser.close()


@pytest.mark.uitest
def test_dataskew_splitkey_upload_check_download(page_url, tmp_path):
    """Split-key panel end to end: upload a .conf, check the key, download
    the patched config via a real expect_download."""
    from playwright.sync_api import expect, sync_playwright

    conf_file = tmp_path / "job.conf"
    conf_file.write_text(SPLITKEY_CONF, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        _connect_sqlite(page)
        panel = page.locator("details",
                             has_text="SeaTunnel split-key check")
        panel.locator("summary").click()
        panel.locator('input[type="file"]').set_input_files(str(conf_file))
        expect(panel.locator("textarea")).to_have_value(SPLITKEY_CONF)

        page.get_by_role("button", name="Check split key",
                         exact=True).click()
        dl_btn = page.get_by_role("button",
                                  name="Download patched config")
        expect(dl_btn).to_be_visible(timeout=20000)
        with page.expect_download() as dl:
            dl_btn.click()
        patched = dl.value
        assert patched.suggested_filename == "seatunnel_patched.conf"
        patched_text = _download_text(patched)
        assert patched_text.strip()
        assert 'partition_column = "id"' in patched_text
        browser.close()


@pytest.mark.uitest
def test_dataskew_runtime_panel(page_url, tmp_path):
    """Runtime panel: rt_btn without inputs shows the localized guard;
    uploading a Spark event log appends the runtime diagnosis section."""
    from playwright.sync_api import expect, sync_playwright

    log_file = tmp_path / "eventlog.json"
    _write_eventlog(log_file)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        panel = page.locator("details", has_text="Runtime diagnosis")
        panel.locator("summary").click()
        page.get_by_role("button", name="Fetch & diagnose",
                         exact=True).click()
        expect(page.get_by_text("Provide both the History Server URL",
                                exact=False)).to_be_visible()

        panel.locator('input[type="file"]').set_input_files(str(log_file))
        report = page.locator(".dsk-report-card")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("Runtime Skew Diagnosis",
                                       timeout=15000)
        browser.close()


@pytest.mark.uitest
def test_dataskew_preset_load_and_sample_verify(page_url, stub_presets):
    """Preset load button fills the form from the saved connection; after
    switching the sample-size select Verify still works."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill(GROUP_SQL)
        page.locator("summary", has_text="Connect data source").click()
        page.get_by_role("button", name="Load saved connections",
                         exact=True).click()
        preset_select = labeled_select(page, "Saved connection")
        expect(preset_select.locator("option",
                                     has_text="pw_demo")).to_have_count(1)
        preset_select.select_option("pw_demo")
        expect(page.get_by_text("Database").locator(
            "xpath=following-sibling::input")).to_have_value(_DEMO_DB)

        page.get_by_role("button", name="Connect", exact=True).click()
        expect(page.get_by_text("Connected", exact=False)).to_be_visible(
            timeout=10000)

        labeled_select(page, "Probe sampling").select_option("1")  # 1% sampling
        page.get_by_role("button", name="Verify Skew (live data)",
                         exact=True).click()
        expect(page.locator(".dsk-report-card")).to_contain_text(
            "Skew Verification", timeout=15000)
        browser.close()



@pytest.mark.uitest
def test_dataskew_dialect_switch_hive(page_url):
    """Ticket 05: non-default dialect (hive; default is spark) still flags
    the COUNT(DISTINCT) single-point aggregation."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        def run():
            page.locator("#dsk-sql-box").fill(DISTINCT_SQL)
            page.get_by_role("button", name="Analyze Skew",
                             exact=True).click()

        assert_dialect_switch(
            page, dialect="hive", run=run,
            report=page.locator(".dsk-report-card"),
            contains="COUNT(DISTINCT)", timeout=10000)
        browser.close()


@pytest.mark.uitest
def test_dataskew_runtime_flink_button(page_url, monkeypatch):
    """The Flink diagnose button posts url+job id and renders the runtime
    section (analyzer mocked; the REST shape is covered by API tests)."""
    from playwright.sync_api import expect, sync_playwright

    from seatunnel_agent.agents.data.data_skew import runtime as rt

    monkeypatch.setattr(
        rt, "analyze_flink",
        lambda url, job: ([rt.StageSkew(stage_id=0, name="Source: orders",
                                        tasks=4, dur_p50=2_000,
                                        dur_max=65_000)],
                          "sync-orders (j-1)"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("summary", has_text="Runtime diagnosis").click()
        page.get_by_text("History Server URL").locator(
            "xpath=following-sibling::input").fill("http://fl:8081")
        page.get_by_text("Application ID").locator(
            "xpath=following-sibling::input").fill("j-1")
        page.get_by_role("button", name="Flink diagnose", exact=True).click()

        report = page.locator(".dsk-report-card")
        expect(report).to_contain_text("sync-orders", timeout=10000)
        expect(report).to_contain_text("Source: orders")
        browser.close()


@pytest.mark.uitest
def test_dataskew_drift_card(page_url):
    """Drift card: seeded splitkey history renders verdict badge + deltas."""
    import os

    from playwright.sync_api import expect, sync_playwright

    from seatunnel_agent.agents.data.data_skew.history import default_history

    # seed the same history file the in-process server reads
    assert os.environ.get("SEATUNNEL_SKEW_HISTORY_PATH")
    h = default_history()
    for top1, val in ((10.0, "CN"), (14.0, "CN"), (28.0, "US")):
        h.log_splitkey("orders", "id", "good", top1_pct=top1, top1_value=val)
    h.log_splitkey("t2", "id", "good", top1_pct=5.0)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        # opening the accordion auto-loads — no refresh click needed
        page.locator("summary", has_text="Skew drift").click()

        expect(page.get_by_text("orders", exact=True)).to_be_visible(
            timeout=10000)
        expect(page.get_by_text("drift", exact=True)).to_be_visible()
        expect(page.get_by_text("no baseline", exact=True)).to_be_visible()
        row = page.locator("div", has_text="top1_pct").last
        expect(row).to_contain_text("12 → 28")
        expect(row).to_contain_text("+16")
        hot = page.locator("div", has_text="hot value changed").last
        expect(hot).to_contain_text("CN → US")
        browser.close()
