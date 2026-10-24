"""Browser smoke for the React /uitest page (seam 6, batch-5b review Q11A).

Serves the built dist + API router in-process (uvicorn thread) so
run_suite can be monkeypatched — the SSE wiring is under test, not the
runner. Deselected by default (needs a browser + built dist):

    pytest -m uitest tests/test_uitest_page.py
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.devops.ui_testing.manifest import MANIFEST


@pytest.fixture(autouse=True)
def _fake_runner(tmp_path, monkeypatch):
    """Seeded history + faked run_suite (the server comes from the shared
    make_page_url factory; runner/report attrs are read per-request)."""
    from seatunnel_agent.agents.devops.ui_testing import runner

    # one seeded history run
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    d = tmp_path / "20260101_000001"
    d.mkdir()
    (d / "result.json").write_text(json.dumps({
        "started_at": "20260101_000001", "suite": "smoke",
        "elapsed_ms": 2000, "tokens": 0,
        "cases": [{"case_id": "H1", "verdict": "PASS"}],
    }), encoding="utf-8")
    # the report carries a script (stat-tile filtering) — the viewer iframe
    # must allow it to run (sandbox="allow-scripts")
    (d / "report.html").write_text(
        "<html><body><div id='ok'></div><script>"
        "document.getElementById('ok').textContent='script-ran'"
        "</script></body></html>",
        encoding="utf-8",
    )

    # fake runner: SSE wiring is the seam, not the browser suite
    def fake_run_suite(suite, case_ids=None, no_llm=True, on_progress=None,
                       **kw):
        cr = SimpleNamespace(verdict="PASS", case_id="F1",
                             title="fake case", elapsed_ms=10)
        on_progress(1, 1, cr)
        rr = SimpleNamespace(
            counts=lambda: {"PASS": 1, "FAIL": 0, "ERROR": 0,
                            "SKIP": 0, "MANUAL": 0, "HEALED": 0},
            elapsed_ms=10)
        rd = tmp_path / "20260101_000002"
        rd.mkdir(exist_ok=True)
        (rd / "report.html").write_text("<html></html>", encoding="utf-8")
        return rr, rd

    monkeypatch.setattr(runner, "run_suite", fake_run_suite)
    from seatunnel_agent.agents.devops.ui_testing import report
    for fn in ("write_json", "write_html", "write_labels_patch"):
        monkeypatch.setattr(report, fn, lambda *a, **k: None)


page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.devops.ui_testing.api:router", "/uitest")


@pytest.mark.uitest
def test_uitest_page_smoke(page_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        # not a white screen; backend meta reached the dropdowns
        expect(page.get_by_role("heading", name="UI Testing Agent")).to_be_visible()
        expect(page.locator("#suite option")).to_have_count(5)
        expect(page.locator("#agent option", has_text="All agents")).to_have_count(1)

        # history list rendered from GET /api/uitest/runs
        history = page.locator(".st-history")
        expect(history).to_be_visible()
        expect(history).to_contain_text("20260101_000001")
        expect(history).to_contain_text("smoke")

        # click Run: SSE progress then done counts (runner faked server-side)
        page.get_by_role("button", name="Run").click()
        expect(page.locator("pre")).to_contain_text("F1", timeout=15000)
        # "PASS 1" appears in the results card AND the history row — assert
        # the summary specifically (scoped), not a page-global text match
        expect(page.get_by_text("PASS 1").first).to_be_visible(timeout=15000)
        expect(page.get_by_text("elapsed 0s")).to_be_visible()

        browser.close()


@pytest.mark.uitest
def test_uitest_report_iframe_runs_scripts(page_url):
    """Viewing a report must not log 'Blocked script execution' — the
    report iframe is sandboxed with allow-scripts so its filter JS works."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="View").first.click()
        frame_el = page.locator("iframe")
        expect(frame_el).to_be_visible(timeout=15000)
        # the script inside the report actually executed
        frame = page.frame_locator("iframe")
        expect(frame.locator("#ok")).to_have_text("script-ran", timeout=15000)

        blocked = [e for e in errors if "Blocked script execution" in e]
        assert not blocked, blocked
        browser.close()
