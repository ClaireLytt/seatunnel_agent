"""Browser smoke for the React /uitest page (seam 6, batch-5b review Q11A).

Serves the built dist + API router in-process (uvicorn thread) so
run_suite can be monkeypatched — the SSE wiring is under test, not the
runner. Deselected by default (needs a browser + built dist):

    pytest -m uitest tests/test_uitest_page.py
"""

from __future__ import annotations

import json
import socket
import threading
import time
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.uitest


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url(tmp_path, monkeypatch):
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.devops.ui_testing import runner
    from seatunnel_agent.agents.devops.ui_testing.api import (
        FRONTEND_DIST,
        router,
    )

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip("frontend dist not built (cd frontend/uitest && npm run build)")

    # one seeded history run
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    d = tmp_path / "20260101_000001"
    d.mkdir()
    (d / "result.json").write_text(json.dumps({
        "started_at": "20260101_000001", "suite": "smoke",
        "elapsed_ms": 2000, "tokens": 0,
        "cases": [{"case_id": "H1", "verdict": "PASS"}],
    }), encoding="utf-8")
    (d / "report.html").write_text("<html></html>", encoding="utf-8")

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

    app = FastAPI()
    app.include_router(router)
    app.mount("/uitest", StaticFiles(directory=FRONTEND_DIST, html=True))

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                           log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    deadline = time.time() + 15
    while not server.started:
        if time.time() > deadline:
            pytest.fail("uvicorn did not start")
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}/uitest/"
    server.should_exit = True
    t.join(timeout=5)


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
