"""Browser tests for the React /pipemigrate page.

Serves the built dist + API router in-process, modeled on
tests/test_dagcheck_page.py. Deselected by default:

    pytest -m uitest tests/test_pipemigrate_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.pipeline_migrate.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "pipemigrate_demo"

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.pipeline_migrate.api:router",
    "/pipemigrate", chdir="root",
    env={"PIPEMIGRATE_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_pipemigrate_page_run_flow(page_url):
    """Demo prefill → Assess directory → jobs, order, shared, stubs."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="Migration Assessor")).to_be_visible()
        assert (page.locator("input").first.input_value()
                == "examples/pipemigrate_demo")
        page.get_by_role("button", name="Assess directory",
                         exact=True).click()

        expect(page.get_by_role(
            "heading", name="Pipeline Migration Assessment")).to_be_visible()
        for section in ("Migration order", "Shared tables",
                        "SeaTunnel config skeletons"):
            expect(page.get_by_role(
                "heading", name=section, exact=False)).to_be_visible()
        # both the sqoop shell and the DataX JSON land on SeaTunnel
        expect(page.get_by_text("sync_orders.sh").first).to_be_visible()
        expect(page.get_by_text("datax_items.json").first).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()
