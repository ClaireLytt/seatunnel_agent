"""Browser tests for the React /slaboard page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_slaboard_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.sla_board.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "slaboard_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.sla_board.api:router", "/slaboard",
    env_var="SLABOARD_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="SLA Board", run_button="Score board",
    expect_texts=['SL002', 'dws_orders_daily'],
    llm_label="LLM SLA update"))
