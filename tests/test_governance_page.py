"""Browser tests for the React /governance overview page.

Serves the built dist with the hygiene router mounted and its history
seeded; the other four stats endpoints 404, which the page renders as
quiet empty cards. Deselected by default:

    pytest -m uitest tests/test_governance_page.py
"""

from __future__ import annotations

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.governance_overview.manifest import MANIFEST


def _seed_hygiene(monkeypatch, tmp_path):
    from seatunnel_agent.agents.data.lineage_hygiene import analyze_sql_text
    from seatunnel_agent.agents.data.lineage_hygiene.history import (
        HygieneLogger,
    )

    sql = ("CREATE TABLE ods.t1 (id INT COMMENT 'i');\n"
           "INSERT INTO dwd.dead SELECT id FROM ods.t1;")
    logger = HygieneLogger(log_dir=tmp_path / "logs")
    logger.log_run(analyze_sql_text(sql), source="cli")
    logger.log_run(analyze_sql_text(sql), source="api")
    monkeypatch.chdir(tmp_path)


page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.lineage_hygiene.api:router",
    "/governance", chdir="tmp", post_setup=_seed_hygiene)


@pytest.mark.uitest
def test_governance_overview_renders(page_url):
    """Seeded hygiene card shows counts and trend; others show empty state."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="Governance Overview")).to_be_visible()
        # seeded agent: run count and totals render
        hygiene = page.get_by_role("heading", name="Warehouse Hygiene")
        expect(hygiene).to_be_visible()
        expect(page.get_by_text("2 runs")).to_be_visible()
        # unseeded agents fall back to the quiet empty state
        expect(page.get_by_text(
            "No runs recorded yet", exact=False).first).to_be_visible()

        # fetch failures on the four unmounted agents are expected; the
        # page must not raise beyond the 404 network notices
        real_errors = [e for e in console_errors
                       if "404" not in e and "Failed to load resource" not in e]
        assert not real_errors, f"console errors: {real_errors}"
        browser.close()
