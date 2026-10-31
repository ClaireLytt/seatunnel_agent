"""Browser tests for the React /kafkalag page.

Serves the built dist + API router in-process, modeled on
tests/test_sampleprofile_page.py. Deselected by default:

    pytest -m uitest tests/test_kafkalag_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.kafka_lag.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "kafkalag_demo"

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.kafka_lag.api:router",
    "/kafkalag", chdir="root",
    env={"KAFKALAG_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_kafkalag_page_run_flow(page_url):
    """Prefilled snapshot → Diagnose → ranked findings."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role(
            "heading", name="Kafka Lag", exact=True).first).to_be_visible()
        page.get_by_role("button", name="Diagnose", exact=True).click()

        # the demo snapshot has a hot stalled partition pair
        expect(page.get_by_text("KL002", exact=True).first).to_be_visible()
        expect(page.get_by_text("orders[2]",
                                exact=False).first).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


nokey_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.kafka_lag.api:router",
    "/kafkalag", chdir="root", neutralize_llm=True,
    env={"KAFKALAG_API_ALLOWED_DIRS": str(DEMO)},
    name="nokey_url")


@pytest.mark.uitest
def test_kafkalag_note_without_key_surfaces_503(nokey_url):
    """LLM note checked without a key -> inline 503, no crash."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(nokey_url, wait_until="networkidle")
        page.get_by_text("LLM ops note", exact=False).click()
        page.get_by_role("button", name="Diagnose", exact=True).click()
        expect(page.get_by_text("API_KEY is not set",
                                exact=False)).to_be_visible(timeout=15000)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()
