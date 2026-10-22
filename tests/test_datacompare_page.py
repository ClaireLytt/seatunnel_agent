"""Browser smoke for the React /datacompare page (ticket 02 skeleton).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_uitest_page.py. Deselected by default (needs a browser +
built dist):

    pytest -m uitest tests/test_datacompare_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import download_text as _download_text
from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.data_comparison.manifest import MANIFEST


def _isolate_stores(monkeypatch, tmp_path):
    """Keep the presets/templates/reports stores (and key file) out of the
    user's home — module-level references patched before app assembly."""
    from seatunnel_agent.agents.data.data_comparison import api as api_mod
    from seatunnel_agent.agents.data.data_comparison import (
        generation as gen_mod,
    )
    from seatunnel_agent.agents.data.data_comparison import presets as presets_mod
    from seatunnel_agent.agents.data.data_comparison import (
        reports_api as reports_mod,
    )
    from seatunnel_agent.agents.data.data_comparison.presets import (
        ConnectionPresetsStore,
    )
    from seatunnel_agent.agents.data.data_comparison.templates_store import (
        ComparisonTemplatesStore,
    )

    # isolate the presets + templates stores (and key file) from the user's home
    monkeypatch.setattr(presets_mod, "_KEY_PATH", tmp_path / "dc_secret.key")
    monkeypatch.setattr(presets_mod, "_cached_key", None)
    presets_store = ConnectionPresetsStore(tmp_path / "dc_connections.json")
    monkeypatch.setattr(api_mod, "_PRESETS_STORE", presets_store)
    # generation.py (env compare) holds its own module-level store reference
    monkeypatch.setattr(gen_mod, "_PRESETS_STORE", presets_store)
    monkeypatch.setattr(gen_mod, "_TEMPLATES_STORE",
                        ComparisonTemplatesStore(tmp_path / "dc_templates.json"))
    # isolate saved reports (also read by /trends via reports_api._REPORTS_DIR)
    monkeypatch.setattr(reports_mod, "_REPORTS_DIR", tmp_path / "dc_reports")


page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.data_comparison.api:router",
    "/datacompare", post_setup=_isolate_stores)


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


# ── ticket 02 (coverage batch): every interactive control gets clicked ──


def _make_dbs(tmp_path) -> None:
    """Two identical SQLite fixtures → deterministic match outcomes."""
    import sqlite3

    for name in ("a.db", "b.db"):
        conn = sqlite3.connect(tmp_path / name)
        conn.execute("CREATE TABLE orders (id INTEGER, val TEXT)")
        conn.executemany("INSERT INTO orders VALUES (?, ?)",
                         [(1, "x"), (2, "y")])
        conn.commit()
        conn.close()


def _connect_both(page, tmp_path) -> None:
    """Connect both sides to the SQLite fixtures and pick `orders`."""
    from playwright.sync_api import expect

    for side, name in (("a", "a.db"), ("b", "b.db")):
        form = page.locator(f"[data-testid=connect-{side}]")
        form.locator(f"#ds-{side}").select_option(label="SQLite")
        form.locator(f"#db-{side}").fill(str(tmp_path / name))
        form.get_by_role("button", name="Connect").click()
        expect(page.locator(f"[data-testid=status-{side}]")).to_contain_text("✅")
        form.locator(f"#table-{side}").select_option("orders")


@pytest.mark.uitest
def test_datacompare_count_sample_aggregate_cards(page_url, tmp_path):
    """Core actions count/sample/aggregate each render their result card."""
    from playwright.sync_api import expect, sync_playwright

    _make_dbs(tmp_path)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        _connect_both(page, tmp_path)

        cards = page.locator("[data-testid=result-cards]")
        for action, title in (("count", "Row Count Comparison"),
                              ("sample", "Sample Data Diff"),
                              ("aggregate", "Aggregate Comparison")):
            btn = page.locator(f"[data-testid=action-{action}]")
            expect(btn).to_be_enabled()
            btn.click()
            expect(cards).to_contain_text(title)
        browser.close()


@pytest.mark.uitest
def test_datacompare_profile_and_batch_actions(page_url, tmp_path):
    """Compound actions profile/batch-count/batch-full render their cards."""
    from playwright.sync_api import expect, sync_playwright

    _make_dbs(tmp_path)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        _connect_both(page, tmp_path)

        cards = page.locator("[data-testid=result-cards]")
        for action, title in (("profile", "Column Profile Comparison"),
                              ("batch-count", "Batch Row Count"),
                              ("batch-full", "Batch Full Comparison")):
            btn = page.locator(f"[data-testid=action-{action}]")
            expect(btn).to_be_enabled()
            btn.click()
            expect(cards).to_contain_text(title)
        browser.close()


@pytest.mark.uitest
def test_datacompare_feature_accordion_runs(page_url, tmp_path):
    """All 8 feature run buttons render their result card (chunked uses
    the Key Columns option as its numeric PK)."""
    from playwright.sync_api import expect, sync_playwright

    _make_dbs(tmp_path)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        _connect_both(page, tmp_path)

        # chunked verification reads Key Columns from the global options
        page.locator("#opt-keys").fill("id")

        cards = page.locator("[data-testid=result-cards]")

        def open_acc(testid):
            page.locator(f"[data-testid={testid}] > button").click()

        # incremental (no key cols in payload → positional sample diff card)
        open_acc("accordion-incremental")
        acc = page.locator("[data-testid=accordion-incremental]")
        acc.locator("input").first.fill("id")
        page.locator("[data-testid=feature-incremental]").click()
        expect(cards).to_contain_text("Key-Based Diff")

        open_acc("accordion-quality")
        page.locator("[data-testid=accordion-quality] input").first.fill(
            "val:not_null>50")
        page.locator("[data-testid=feature-quality]").click()
        expect(cards).to_contain_text("Quality Check Result")

        open_acc("accordion-skew")
        page.locator("[data-testid=accordion-skew] input").first.fill("val")
        page.locator("[data-testid=feature-skew]").click()
        expect(cards).to_contain_text("Data Skew Analysis")

        open_acc("accordion-checksum")
        page.locator("[data-testid=accordion-checksum] input").first.fill("val")
        page.locator("[data-testid=feature-checksum]").click()
        expect(cards).to_contain_text("Checksum Comparison")
        page.locator("[data-testid=feature-chunked]").click()
        expect(cards).to_contain_text("Chunked Verification")

        open_acc("accordion-partition")
        page.locator("[data-testid=accordion-partition] input").first.fill("val")
        page.locator("[data-testid=feature-partition]").click()
        expect(cards).to_contain_text("Partition Comparison")

        open_acc("accordion-custom-agg")
        page.locator("[data-testid=accordion-custom-agg] textarea").fill(
            "s=SUM(id)")
        page.locator("[data-testid=feature-custom-agg]").click()
        expect(cards).to_contain_text("Custom Aggregate Comparison")

        open_acc("accordion-sql")
        sqls = page.locator("[data-testid=accordion-sql] textarea")
        sqls.nth(0).fill("SELECT COUNT(*) AS c FROM orders")
        sqls.nth(1).fill("SELECT COUNT(*) AS c FROM orders")
        page.locator("[data-testid=feature-sql]").click()
        expect(cards).to_contain_text("SQL Result Comparison")
        browser.close()


@pytest.mark.uitest
def test_datacompare_generation_card_buttons(page_url, tmp_path):
    """GenerationCard: sync config (+ real .conf download), diff SQL and
    lineage each render deterministically."""
    from playwright.sync_api import expect, sync_playwright

    _make_dbs(tmp_path)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        _connect_both(page, tmp_path)

        cards = page.locator("[data-testid=result-cards]")

        page.locator("[data-testid=sync-card] > button").click()
        # scope below the accordion header (which shares the title text)
        page.locator("[data-testid=sync-card] div").get_by_role(
            "button", name="Generate Sync Config").click()
        expect(cards).to_contain_text("Sync config generated")
        with page.expect_download() as dl_info:
            page.locator("[data-testid=sync-download]").click()
        download = dl_info.value
        assert download.suggested_filename == "seatunnel_sync.conf"
        text = _download_text(download)
        assert "orders" in text and text.strip()

        # diff SQL without a prior keyed diff → deterministic notice
        page.get_by_role("button", name="Generate Diff SQL").click()
        expect(cards).to_contain_text("No keyed diff result to generate SQL from")

        page.locator("[data-testid=lineage-card] > button").click()
        page.locator("#lineage-sql").fill(
            "INSERT INTO orders SELECT * FROM src_orders")
        page.locator("[data-testid=lineage-card] div").get_by_role(
            "button", name="Upstream Dependencies").click()
        expect(cards).to_contain_text("Upstream Dependencies")
        expect(cards).to_contain_text("src_orders")
        browser.close()


@pytest.mark.uitest
def test_datacompare_generate_diff_sql_happy_path(page_url, tmp_path):
    """Generate Diff SQL after a keyed diff: side B is mutated so the
    keyed diff carries modified + added rows, and the Generated SQL card
    shows real repair statements (not the empty-state notice)."""
    import sqlite3

    from playwright.sync_api import expect, sync_playwright

    _make_dbs(tmp_path)
    # drift side B: one modified value + one extra row
    conn = sqlite3.connect(tmp_path / "b.db")
    conn.execute("UPDATE orders SET val = 'changed' WHERE id = 2")
    conn.execute("INSERT INTO orders VALUES (3, 'extra')")
    conn.commit()
    conn.close()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        _connect_both(page, tmp_path)

        cards = page.locator("[data-testid=result-cards]")

        # keyed diff first: Key Columns + incremental feature, as in
        # test_datacompare_feature_accordion_runs
        page.locator("#opt-keys").fill("id")
        page.locator("[data-testid=accordion-incremental] > button").click()
        page.locator(
            "[data-testid=accordion-incremental] input").first.fill("id")
        page.locator("[data-testid=feature-incremental]").click()
        expect(cards).to_contain_text("Key-Based Diff")

        # now the session holds a keyed diff for the SQL generator
        page.locator("[data-testid=sync-card] > button").click()
        page.get_by_role("button", name="Generate Diff SQL").click()
        expect(cards).to_contain_text("Generated SQL")
        expect(cards).to_contain_text("UPDATE")
        expect(cards).to_contain_text("orders")
        browser.close()


@pytest.mark.uitest
def test_datacompare_preset_save_b_and_env_compare(page_url, tmp_path):
    """Save Preset (B) persists side B's form; Compare Environments then
    resolves both env presets and renders real comparison cards."""
    from playwright.sync_api import expect, sync_playwright

    _make_dbs(tmp_path)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        _connect_both(page, tmp_path)

        card = page.locator("[data-testid=presets-card]")
        card.get_by_role("button", name="Presets").click()
        card.locator("#preset-name").fill("pa")
        card.locator("#preset-env").fill("dev")
        card.get_by_role("button", name="Save Preset (A)").click()
        expect(page.locator("[data-testid=preset-status]")).to_contain_text(
            "Preset saved: pa")
        card.locator("#preset-name").fill("pb")
        card.locator("#preset-env").fill("prod")
        card.get_by_role("button", name="Save Preset (B)").click()
        expect(page.locator("[data-testid=preset-status]")).to_contain_text(
            "Preset saved: pb")
        expect(card.locator("#preset-load-b option",
                            has_text="pb (prod)")).to_have_count(1)

        page.locator("[data-testid=env-card] > button").click()
        page.locator("#env-a").fill("dev")
        page.locator("#env-b").fill("prod")
        page.locator("#env-table").fill("orders")
        page.get_by_role("button", name="Compare Environments").click()
        cards = page.locator("[data-testid=result-cards]")
        expect(cards).to_contain_text("Multi-Environment Result")
        expect(cards).to_contain_text("Row Count Comparison")
        browser.close()


@pytest.mark.uitest
def test_datacompare_reports_cycle_and_trends(page_url, tmp_path):
    """ReportsCard save→refresh→load→diff closes the loop; Trend show then
    charts the saved history."""
    from playwright.sync_api import expect, sync_playwright

    _make_dbs(tmp_path)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        _connect_both(page, tmp_path)

        # a comparison result to persist
        page.locator("[data-testid=action-count]").click()
        cards = page.locator("[data-testid=result-cards]")
        expect(cards).to_contain_text("Row Count Comparison")

        card = page.locator("[data-testid=reports-card]")
        card.locator("xpath=./button").click()  # open (triggers refresh)
        card.get_by_role("button", name="Save Report").click()
        expect(page.locator("[data-testid=report-status]")).to_contain_text(
            "Report saved")
        # second save needs a distinct filename for the diff; the server
        # names reports compare_<a>_vs_<b>_<UTC-seconds>.json with no
        # client-settable name (reports_api.save_report), so waiting out
        # the 1-second timestamp resolution is the deterministic option.
        page.wait_for_timeout(1100)
        card.get_by_role("button", name="Save Report").click()
        card.get_by_role("button", name="Refresh").click()
        expect(card.locator("#report-load option")).to_have_count(3)  # blank + 2

        names = card.locator("#report-load option").all_text_contents()
        newest, oldest = names[1], names[2]
        card.locator("#report-load").select_option(newest)
        expect(cards).to_contain_text("Report loaded")
        expect(cards).to_contain_text("Row Count Comparison")

        card.locator("#report-old").select_option(oldest)
        card.locator("#report-new").select_option(newest)
        card.get_by_role("button", name="Report Diff").click()
        # identical snapshots → the diff endpoint's deterministic verdict
        expect(cards).to_contain_text("No changes between reports")

        # trends read the same saved-report history
        page.locator("[data-testid=trends-card] > button").click()
        page.locator("[data-testid=trend-show]").click()
        expect(page.locator("[data-testid=trend-charts]")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_datacompare_templates_delete_and_batch_run(page_url, tmp_path):
    """TemplatesCard: delete the selected template; batch-run the rest."""
    from playwright.sync_api import expect, sync_playwright

    _make_dbs(tmp_path)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        _connect_both(page, tmp_path)

        card = page.locator("[data-testid=templates-card]")
        card.locator("xpath=./button").click()  # open
        for name in ("t-del", "t-run"):
            page.locator("#template-name").fill(name)
            card.get_by_role("button", name="Save Template").click()
            expect(page.locator("[data-testid=template-status]")).to_contain_text(
                "Template saved")

        # wait out the post-save refresh (it resets the selection)
        expect(page.locator("#template-load option")).to_have_count(3)
        page.locator("#template-load").select_option("t-del")
        expect(page.locator("#template-load")).to_have_value("t-del")
        card.get_by_role("button", name="delete").click()
        expect(page.locator("[data-testid=template-status]")).to_contain_text(
            "Template deleted")
        expect(page.locator("#template-load option", has_text="t-del")
               ).to_have_count(0)

        page.locator("#batch-templates").select_option(["t-run"])
        card.get_by_role("button", name="Run Selected").click()
        cards = page.locator("[data-testid=result-cards]")
        expect(cards).to_contain_text("Batch Template Results")
        expect(cards).to_contain_text("t-run")
        browser.close()


@pytest.mark.uitest
def test_datacompare_schedule_start_stop(page_url, tmp_path):
    """Schedule start arms the timer (status ●); stop disarms it (○)."""
    from playwright.sync_api import expect, sync_playwright

    _make_dbs(tmp_path)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        _connect_both(page, tmp_path)

        page.locator("[data-testid=schedule-card] > button").click()
        page.locator("[data-testid=schedule-interval]").select_option("5")
        status = page.locator("[data-testid=schedule-status]")

        page.locator("[data-testid=schedule-start]").click()
        expect(status).to_contain_text("Scheduled: next run in 5 min")
        expect(status).to_contain_text("●")

        page.locator("[data-testid=schedule-stop]").click()
        expect(status).to_contain_text("Schedule stopped")
        expect(status).to_contain_text("○")
        browser.close()


@pytest.mark.uitest
def test_datacompare_export_downloads_and_standalone_report(page_url, tmp_path):
    """Export CSV/Excel really download; View Report opens the standalone
    HTML page in a new tab."""
    from playwright.sync_api import expect, sync_playwright

    _make_dbs(tmp_path)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        _connect_both(page, tmp_path)

        page.locator("[data-testid=action-count]").click()
        expect(page.locator("[data-testid=result-cards]")).to_contain_text(
            "Row Count Comparison")

        toolbar = page.locator("[data-testid=results-toolbar]")
        with page.expect_download() as dl_info:
            toolbar.get_by_role("link", name="Export CSV").click()
        csv_dl = dl_info.value
        assert csv_dl.suggested_filename.endswith(".csv")
        assert "row count" in _download_text(csv_dl).lower()

        with page.expect_download() as dl_info:
            toolbar.get_by_role("link", name="Export Excel").click()
        xlsx_dl = dl_info.value
        assert xlsx_dl.suggested_filename.endswith(".xlsx")
        assert Path(xlsx_dl.path()).stat().st_size > 0

        with page.expect_popup() as pop_info:
            toolbar.get_by_role("link", name="View Report").click()
        report_page = pop_info.value
        report_page.wait_for_load_state()
        expect(report_page.locator("h1")).to_contain_text(
            "Data Comparison Report")
        browser.close()
