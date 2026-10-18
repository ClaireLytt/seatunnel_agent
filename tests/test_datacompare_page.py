"""Browser smoke for the React /datacompare page (ticket 02 skeleton).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_uitest_page.py. Deselected by default (needs a browser +
built dist):

    pytest -m uitest tests/test_datacompare_page.py
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.uitest

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "datacompare" / "dist"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url(tmp_path, monkeypatch):
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.data.data_comparison import api as api_mod
    from seatunnel_agent.agents.data.data_comparison import presets as presets_mod
    from seatunnel_agent.agents.data.data_comparison.api import router
    from seatunnel_agent.agents.data.data_comparison.presets import (
        ConnectionPresetsStore,
    )

    # isolate the presets store (and its key file) from the user's home
    monkeypatch.setattr(presets_mod, "_KEY_PATH", tmp_path / "dc_secret.key")
    monkeypatch.setattr(presets_mod, "_cached_key", None)
    monkeypatch.setattr(api_mod, "_PRESETS_STORE",
                        ConnectionPresetsStore(tmp_path / "dc_connections.json"))

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip(
            "frontend dist not built (cd frontend && npm run build --workspace datacompare)")

    app = FastAPI()
    app.include_router(router)
    app.mount("/datacompare", StaticFiles(directory=FRONTEND_DIST, html=True))

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
    yield f"http://127.0.0.1:{port}/datacompare/"
    server.should_exit = True
    t.join(timeout=5)


@pytest.mark.uitest
def test_datacompare_page_smoke(page_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        # shell rendered; backend meta reached the datasource dropdowns
        expect(page.get_by_role("heading", name="Data Comparison")).to_be_visible()
        for side in ("a", "b"):
            form = page.locator(f"[data-testid=connect-{side}]")
            expect(form).to_be_visible()
            expect(form.locator(f"#ds-{side} option", has_text="SQLite")).to_have_count(1)
            expect(form.get_by_role("button", name="Connect")).to_be_visible()
        # results panel placeholder present
        expect(page.get_by_role("heading", name="Results")).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_datacompare_options_reset(page_url):
    """Options block: stratified column is conditional; reset restores defaults."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        card = page.locator("[data-testid=options-card]")
        expect(card.locator("#opt-where")).to_be_visible()  # open by default

        card.locator("#opt-where").fill("date > '2024-01-01'")
        card.locator("#opt-threshold").fill("5%")
        expect(card.locator("#opt-stratified")).to_have_count(0)
        card.locator("#opt-strategy").select_option("STRATIFIED")
        expect(card.locator("#opt-stratified")).to_be_visible()
        card.locator("#opt-stratified").fill("region")
        card.locator("#opt-masking").uncheck()

        card.get_by_role("button", name="Reset Options").click()
        expect(card.locator("#opt-where")).to_have_value("")
        expect(card.locator("#opt-threshold")).to_have_value("")
        expect(card.locator("#opt-strategy")).to_have_value("TOP N")
        expect(card.locator("#opt-stratified")).to_have_count(0)
        expect(card.locator("#opt-masking")).to_be_checked()
        browser.close()


@pytest.mark.uitest
def test_datacompare_presets_round_trip(page_url):
    """Save a preset from side A, load it into side B, delete it."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        # fill side A's connect form (sqlite: database only)
        form_a = page.locator("[data-testid=connect-a]")
        form_a.locator("#ds-a").select_option(label="SQLite")
        form_a.locator("#db-a").fill("/tmp/demo.db")

        card = page.locator("[data-testid=presets-card]")
        card.get_by_role("button", name="Presets").click()  # accordion toggle
        card.locator("#preset-name").fill("demo")
        card.locator("#preset-env").fill("dev")
        card.get_by_role("button", name="Save Preset (A)").click()
        expect(page.locator("[data-testid=preset-status]")).to_contain_text("Preset saved")
        expect(card.locator("#preset-load-a option", has_text="demo (dev)")).to_have_count(1)

        # auto-apply on select fills side B's form
        card.locator("#preset-load-b").select_option(label="demo (dev)")
        form_b = page.locator("[data-testid=connect-b]")
        expect(form_b.locator("#db-b")).to_have_value("/tmp/demo.db")
        expect(form_b.locator("#ds-b")).to_have_value("sqlite")

        # delete the preset selected in the A dropdown
        card.locator("#preset-load-a").select_option(label="demo (dev)")
        card.get_by_role("button", name="delete").click()
        expect(page.locator("[data-testid=preset-status]")).to_contain_text("Preset deleted")
        expect(card.locator("#preset-load-a option")).to_have_count(1)  # blank only
        browser.close()
