"""Browser tests for the React /games page (mind games).

The page is pure browser-side (no API of its own); the hygiene router is
mounted only because the page-server fixture requires one. Deselected by
default:

    pytest -m uitest tests/test_mind_games_page.py
"""

from __future__ import annotations

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.ai.mind_games.manifest import MANIFEST

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.lineage_hygiene.api:router",
    "/games", chdir="root")


@pytest.mark.uitest
def test_games_page_smoke(page_url):
    """Chrome renders with three tabs; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading", name="Mind Games")).to_be_visible()
        for tab in ("Learned Optimism", "Signature Strengths",
                    "Five Questions"):
            expect(page.get_by_role("button", name=tab,
                                    exact=True)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_games_optimism_round(page_url):
    """Answering nine cards reaches the verdict with a replay button."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        for _ in range(9):
            page.locator("button.text-left").first.click()
        expect(page.get_by_text("Reading")).to_be_visible(timeout=10000)
        expect(page.get_by_role("button", name="Play again",
                                exact=True)).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_games_five_questions_reveal(page_url):
    """Filling the five questions reveals five score bars."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Five Questions", exact=True).click()
        inputs = page.locator("input")
        for i, text in enumerate(["laughing with a friend", "painting",
                                  "my best friend", "keeping a journal",
                                  "finished a small project"]):
            inputs.nth(i).fill(text)
        page.get_by_role("button", name="Reveal my pillars",
                         exact=True).click()
        expect(page.get_by_text("P · Positive Emotion")).to_be_visible()
        expect(page.get_by_text("A · Accomplishment")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_games_three_good_things_lights_the_lamp(page_url):
    """Writing tonight's three things lights the lamp and feeds the
    landing page's garden-corner notebook (shared localStorage key)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Three Good Things",
                         exact=True).click()
        expect(page.get_by_text(
            "The first evening lights the lamp.")).to_be_visible()
        inputs = page.locator("input")
        for i, text in enumerate(["a good walk", "warm tea",
                                  "finished the ledger"]):
            inputs.nth(i * 2).fill(text)
        page.get_by_role("button", name="Set down tonight",
                         exact=True).click()

        expect(page.get_by_text("1 consecutive evenings")).to_be_visible()
        expect(page.get_by_text("Tonight is written",
                                exact=False)).to_be_visible()
        notes = page.evaluate(
            "() => JSON.parse(localStorage.getItem('st_garden.notes.v1'))")
        assert notes and "a good walk" in notes[-1]["text"]
        browser.close()
