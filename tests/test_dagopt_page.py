"""Browser tests for the React /dagopt page.

Serves the built dist + API router in-process, modeled on
tests/test_dagcheck_page.py. Deselected by default:

    pytest -m uitest tests/test_dagopt_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.dag_optimize.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "dagopt_demo"

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.dag_optimize.api:router",
    "/dagopt", chdir="root",
    env={"DAGOPT_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_dagopt_page_run_flow(page_url):
    """Demo prefill → Analyze file → full report; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="DAG Optimizer")).to_be_visible()
        assert (page.locator("input").first.input_value()
                == "examples/dagopt_demo/dag.json")
        page.locator("input").nth(1).fill("30")  # SLA duration
        page.get_by_role("button", name="Analyze file", exact=True).click()

        expect(page.get_by_role(
            "heading", name="DAG Dependency Optimization")).to_be_visible()
        # the SLA verdict line names the minimal speed-up set
        expect(page.get_by_text("Deadline 30: reachable",
                                exact=False)).to_be_visible()
        expect(page.get_by_role("heading", name="Critical path",
                                exact=True)).to_be_visible()
        for section in ("Redundant serial dependencies", "Parallel waves",
                        "Bottleneck sensitivity",
                        "Makespan by worker count", "Optimized DAG"):
            expect(page.get_by_role(
                "heading", name=section, exact=False)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()
