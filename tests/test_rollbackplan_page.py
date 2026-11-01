"""Browser tests for the React /rollbackplan page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_rollbackplan_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.rollback_plan.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "rollbackplan_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.rollback_plan.api:router", "/rollbackplan",
    env_var="ROLLBACKPLAN_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Rollback Plan", run_button="Plan rollback",
    expect_texts=['dws.orders_daily', 'snap_dwd_orders_20261030'],
    llm_label="LLM incident update"))
