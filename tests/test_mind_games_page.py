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


@pytest.mark.uitest
def test_games_optimism_ledger_one_entry_per_day(page_url):
    """A retake on the same day overwrites tonight's ledger entry: seed a
    stale entry for today plus one older day, complete a round, and the
    ledger still holds exactly one row per day with today's overwritten."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        page.evaluate(
            """() => {
              const d = new Date();
              const day = `${d.getFullYear()}-${String(d.getMonth() + 1)
                .padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
              localStorage.setItem('st_games.optledger.v1', JSON.stringify(
                [{ day: '2026-10-01', score: 50 }, { day, score: -1 }]));
            }""")
        page.reload(wait_until="networkidle")

        for _ in range(9):
            page.locator("button.text-left").first.click()
        expect(page.get_by_text("Reading")).to_be_visible(timeout=10000)

        ledger = page.evaluate(
            "() => JSON.parse(localStorage.getItem('st_games.optledger.v1'))")
        days = [e["day"] for e in ledger]
        assert len(days) == len(set(days)), f"duplicate days: {days}"
        assert len(ledger) == 2                     # old day kept, today once
        today_rows = [e for e in ledger if e["score"] != 50]
        assert today_rows[0]["score"] >= 0          # seeded -1 was overwritten
        browser.close()


@pytest.mark.uitest
def test_games_breathing_renders_and_starts(page_url):
    """The breathing tab shows the ring, and Begin enters the first phase."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Breathing", exact=True).click()
        expect(page.get_by_text("4 · 7 · 8")).to_be_visible()
        page.get_by_role("button", name="Begin", exact=True).click()
        expect(page.get_by_text("Breathe in", exact=True)).to_be_visible()
        expect(page.get_by_text("Round 1 of 3")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_games_suitcase_round_trip(page_url):
    """Pack on one profile, unpack on a fresh one: records merge, never
    delete (the fresh profile's own evening survives)."""
    import json
    import pathlib
    import tempfile

    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        page.evaluate(
            """() => {
              localStorage.setItem('st_games.three.v1', JSON.stringify(
                [{ day: '2026-10-20', items: [{ what: 'packed', why: '' }] }]));
              localStorage.setItem('st_garden.notes.v1', JSON.stringify(
                [{ day: '2026-10-20', text: 'packed note' }]));
            }""")
        page.reload(wait_until="networkidle")
        with page.expect_download() as dl:
            page.get_by_text("Pack the suitcase", exact=True).click()
        path = str(pathlib.Path(tempfile.gettempdir()) / "mg-suitcase.json")
        dl.value.save_as(path)
        bag = json.loads(open(path, encoding="utf-8").read())
        assert bag["st_suitcase"] == 1
        assert bag["st_games.three.v1"][0]["day"] == "2026-10-20"
        browser.close()

        # fresh context = another browser profile with its own evening
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        page.evaluate(
            """() => {
              localStorage.setItem('st_games.three.v1', JSON.stringify(
                [{ day: '2026-10-21', items: [{ what: 'mine', why: '' }] }]));
            }""")
        page.reload(wait_until="networkidle")
        page.locator("input[type=file]").set_input_files(path)
        expect(page.get_by_text("merged", exact=False)).to_be_visible()
        merged = page.evaluate(
            "() => JSON.parse(localStorage.getItem('st_games.three.v1'))")
        days = sorted(e["day"] for e in merged)
        assert days == ["2026-10-20", "2026-10-21"]   # merged, nothing lost
        notes = page.evaluate(
            "() => JSON.parse(localStorage.getItem('st_garden.notes.v1'))")
        assert notes and notes[0]["text"] == "packed note"
        browser.close()
