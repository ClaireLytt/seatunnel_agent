"""Browser tests for the React /slowquery page.

Serves the built dist + API router in-process, modeled on
tests/test_dagcheck_page.py. Deselected by default:

    pytest -m uitest tests/test_slowquery_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.slow_query.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "slowquery_demo"

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.slow_query.api:router",
    "/slowquery", chdir="root",
    env={"SLOWQUERY_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_slowquery_page_run_flow(page_url):
    """Prefilled metrics + baseline → Diagnose → ranked causes."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="Slow-Query RCA")).to_be_visible()
        page.get_by_role("button", name="Diagnose", exact=True).click()

        expect(page.get_by_role(
            "heading", name="Slow-Query Root Cause")).to_be_visible()
        expect(page.get_by_text("SQ001", exact=True)).to_be_visible()
        # the baseline regression figure made it into the header
        expect(page.get_by_text("4.19x", exact=False)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()
