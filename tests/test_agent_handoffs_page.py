"""Browser tests for the cross-page handoffs (sessionStorage).

Two servers, each mounting the source page next to the target page:

* /backfill    → /backfillsql  (plan JSON → spec skeletons, auto-run)
* /pipemigrate → /dagopt       (migration DAG → analysis, auto-run)

Deselected by default:  pytest -m uitest tests/test_agent_handoffs_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.backfill.manifest import (
    MANIFEST as BACKFILL_MF,
)
from seatunnel_agent.agents.data.backfill_sql.manifest import (
    MANIFEST as BACKFILLSQL_MF,
)
from seatunnel_agent.agents.data.dag_optimize.manifest import (
    MANIFEST as DAGOPT_MF,
)
from seatunnel_agent.agents.data.pipeline_migrate.manifest import (
    MANIFEST as PIPEMIGRATE_MF,
)

ROOT = Path(__file__).resolve().parents[1]

backfill_pair_url = make_page_url(
    BACKFILLSQL_MF,
    "seatunnel_agent.agents.data.backfill_sql.api:router",
    "/backfillsql", chdir="root",
    env={"BACKFILL_API_ALLOWED_DIRS": str(ROOT / "examples" / "backfill_demo"),
         "BACKFILLSQL_API_ALLOWED_DIRS":
             str(ROOT / "examples" / "backfillsql_demo")},
    extra_mounts=[("/backfill", BACKFILL_MF)],
    extra_routers=["seatunnel_agent.agents.data.backfill.api:router"],
    name="backfill_pair_url")

migrate_pair_url = make_page_url(
    DAGOPT_MF,
    "seatunnel_agent.agents.data.dag_optimize.api:router",
    "/dagopt", chdir="root",
    env={"PIPEMIGRATE_API_ALLOWED_DIRS":
             str(ROOT / "examples" / "pipemigrate_demo"),
         "DAGOPT_API_ALLOWED_DIRS": str(ROOT / "examples" / "dagopt_demo")},
    extra_mounts=[("/pipemigrate", PIPEMIGRATE_MF)],
    extra_routers=["seatunnel_agent.agents.data.pipeline_migrate.api:router"],
    name="migrate_pair_url")


@pytest.mark.uitest
def test_backfill_plan_hands_off_to_backfillsql(backfill_pair_url):
    """Plan on /backfill → handoff button → specs auto-run on /backfillsql."""
    from playwright.sync_api import expect, sync_playwright

    base = backfill_pair_url.rsplit("/backfillsql", 1)[0]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"{base}/backfill/", wait_until="networkidle")
        page.get_by_role("button", name="Plan file", exact=True).click()
        handoff = page.get_by_role(
            "button", name="Generate backfill SQL specs from this plan")
        expect(handoff).to_be_visible()
        handoff.click()
        page.wait_for_url("**/backfillsql/")
        expect(page.get_by_role(
            "heading", name="Backfill spec skeletons",
            exact=False)).to_be_visible()
        # the handed-over plan's tables appear in the spec JSON
        content = page.content()
        assert "ods.items" in content and "ads.sales_report" in content
        browser.close()


@pytest.mark.uitest
def test_pipemigrate_hands_off_migration_dag_to_dagopt(migrate_pair_url):
    """Assess on /pipemigrate → handoff → DAG analysis auto-runs on /dagopt."""
    from playwright.sync_api import expect, sync_playwright

    base = migrate_pair_url.rsplit("/dagopt", 1)[0]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"{base}/pipemigrate/", wait_until="networkidle")
        page.get_by_role("button", name="Assess directory",
                         exact=True).click()
        handoff = page.get_by_role(
            "button", name="Estimate the migration itself in the "
                           "DAG Optimizer")
        expect(handoff).to_be_visible()
        handoff.click()
        page.wait_for_url("**/dagopt/")
        expect(page.get_by_role(
            "heading", name="DAG Dependency Optimization")).to_be_visible()
        # migration jobs became DAG tasks
        assert "build_sales.hql" in page.content()
        browser.close()
