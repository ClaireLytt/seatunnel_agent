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

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "data_comparison" / "dist"


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
    from seatunnel_agent.agents.data.data_comparison import (
        generation as gen_mod,
    )
    from seatunnel_agent.agents.data.data_comparison import presets as presets_mod
    from seatunnel_agent.agents.data.data_comparison.api import router
    from seatunnel_agent.agents.data.data_comparison.presets import (
        ConnectionPresetsStore,
    )
    from seatunnel_agent.agents.data.data_comparison.templates_store import (
        ComparisonTemplatesStore,
    )

    # isolate the presets + templates stores (and key file) from the user's home
    monkeypatch.setattr(presets_mod, "_KEY_PATH", tmp_path / "dc_secret.key")
    monkeypatch.setattr(presets_mod, "_cached_key", None)
    monkeypatch.setattr(api_mod, "_PRESETS_STORE",
                        ConnectionPresetsStore(tmp_path / "dc_connections.json"))
    monkeypatch.setattr(gen_mod, "_TEMPLATES_STORE",
                        ComparisonTemplatesStore(tmp_path / "dc_templates.json"))

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip(
            "frontend dist not built (cd frontend && npm run build --workspace data_comparison)")

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

        # ticket 03: core action buttons present and disabled until ready
        for action in ("schema", "count", "sample", "aggregate"):
            btn = page.locator(f"[data-testid=action-{action}]")
            expect(btn).to_be_visible()
            expect(btn).to_be_disabled()

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
def test_datacompare_options_reset_covers_legacy_targets(page_url):
    """Reset Options also clears webhook / alert rules / template name /
    schedule interval / lineage SQL / env fields (legacy 27-output reset,
    inventory ui.py:2142-2151)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        def open_card(testid):
            page.locator(f"[data-testid={testid}] > button").click()

        open_card("webhook-card")
        page.locator("[data-testid=webhook-url]").fill("https://x.example/h")
        page.locator("[data-testid=webhook-on-fail]").check()
        open_card("trends-card")
        page.locator("[data-testid=alert-rules]").fill("delta>100:3")
        open_card("templates-card")
        page.locator("#template-name").fill("tmp-name")
        open_card("schedule-card")
        page.locator("[data-testid=schedule-interval]").select_option("5")
        open_card("lineage-card")
        page.locator("#lineage-sql").fill("SELECT * FROM t")
        open_card("env-card")
        page.locator("#env-a").fill("dev")
        page.locator("#env-b").fill("prod")
        page.locator("#env-table").fill("orders")

        page.get_by_role("button", name="Reset Options").click()

        expect(page.locator("[data-testid=webhook-url]")).to_have_value("")
        expect(page.locator("[data-testid=webhook-on-fail]")).not_to_be_checked()
        expect(page.locator("[data-testid=alert-rules]")).to_have_value("")
        expect(page.locator("#template-name")).to_have_value("")
        expect(page.locator("[data-testid=schedule-interval]")).to_have_value("15")
        expect(page.locator("#lineage-sql")).to_have_value("")
        expect(page.locator("#env-a")).to_have_value("")
        expect(page.locator("#env-b")).to_have_value("")
        expect(page.locator("#env-table")).to_have_value("")
        browser.close()


@pytest.mark.uitest
def test_datacompare_template_saves_feature_fields(page_url):
    """watermark_column + quality_rules round-trip through a template
    (save reads the live accordion values; load restores them)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("[data-testid=accordion-incremental] > button").click()
        watermark = page.locator("[data-testid=accordion-incremental] input").first
        watermark.fill("updated_at")
        page.locator("[data-testid=accordion-quality] > button").click()
        quality = page.locator("[data-testid=accordion-quality] input").first
        quality.fill("name:not_null>95")

        page.locator("[data-testid=templates-card] > button").click()
        page.locator("#template-name").fill("t-fields")
        page.get_by_role("button", name="Save Template").click()
        expect(page.locator("[data-testid=template-status]")).to_contain_text(
            "Template saved")

        # reset wipes the accordion fields; the template must restore them
        page.get_by_role("button", name="Reset Options").click()
        expect(watermark).to_have_value("")

        page.locator("#template-load").select_option("t-fields")
        page.get_by_role("button", name="Load Template").click()
        expect(watermark).to_have_value("updated_at")
        expect(quality).to_have_value("name:not_null>95")
        browser.close()


@pytest.mark.uitest
def test_datacompare_tab_fills_placeholder(page_url):
    """Tab on an empty input fills in its placeholder (legacy tab_fill.js)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        where = page.locator("#opt-where")
        where.click()
        page.keyboard.press("Tab")
        expect(where).to_have_value("e.g. date > '2024-01-01'")

        # a non-empty input keeps normal Tab behavior
        threshold = page.locator("#opt-threshold")
        threshold.fill("5%")
        threshold.click()
        page.keyboard.press("Tab")
        expect(threshold).to_have_value("5%")
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


@pytest.mark.uitest
def test_datacompare_core_action_renders_cards(page_url, tmp_path):
    """Connect two SQLite fixtures, run Schema Diff, see the server card."""
    import sqlite3

    from playwright.sync_api import expect, sync_playwright

    for name in ("a.db", "b.db"):
        conn = sqlite3.connect(tmp_path / name)
        conn.execute("CREATE TABLE orders (id INTEGER, val TEXT)")
        conn.execute("INSERT INTO orders VALUES (1, 'x')")
        conn.commit()
        conn.close()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        for side, name in (("a", "a.db"), ("b", "b.db")):
            form = page.locator(f"[data-testid=connect-{side}]")
            form.locator(f"#ds-{side}").select_option(label="SQLite")
            form.locator(f"#db-{side}").fill(str(tmp_path / name))
            form.get_by_role("button", name="Connect").click()
            expect(page.locator(f"[data-testid=status-{side}]")).to_contain_text("✅")
            form.locator(f"#table-{side}").select_option("orders")

        schema_btn = page.locator("[data-testid=action-schema]")
        expect(schema_btn).to_be_enabled()
        schema_btn.click()
        cards = page.locator("[data-testid=result-cards]")
        expect(cards).to_contain_text("Schema Comparison")
        expect(cards).to_contain_text("Schemas are identical")
        browser.close()


@pytest.mark.uitest
def test_datacompare_compare_all_streams_to_cards(page_url, tmp_path):
    """Compare All streams SSE progress and renders the summary card."""
    import sqlite3

    from playwright.sync_api import expect, sync_playwright

    for name in ("a.db", "b.db"):
        conn = sqlite3.connect(tmp_path / name)
        conn.execute("CREATE TABLE orders (id INTEGER, val TEXT)")
        conn.execute("INSERT INTO orders VALUES (1, 'x')")
        conn.commit()
        conn.close()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        for side, name in (("a", "a.db"), ("b", "b.db")):
            form = page.locator(f"[data-testid=connect-{side}]")
            form.locator(f"#ds-{side}").select_option(label="SQLite")
            form.locator(f"#db-{side}").fill(str(tmp_path / name))
            form.get_by_role("button", name="Connect").click()
            expect(page.locator(f"[data-testid=status-{side}]")).to_contain_text("✅")
            form.locator(f"#table-{side}").select_option("orders")

        all_btn = page.locator("[data-testid=action-all]")
        expect(all_btn).to_be_enabled()
        all_btn.click()
        # while running, every compound button is disabled (double-trigger guard)
        expect(page.locator("[data-testid=action-batch-count]")).to_be_disabled()
        cards = page.locator("[data-testid=result-cards]")
        expect(cards).to_contain_text("Comparison Summary")
        expect(cards).to_contain_text("Column Profile Comparison")
        browser.close()
