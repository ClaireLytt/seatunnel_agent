"""Browser tests for the React /offboardplan page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_offboardplan_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.offboard_plan.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "offboardplan_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.offboard_plan.api:router",
    "/offboardplan",
    env_var="OFFBOARDPLAN_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Offboarding Plan", run_button="Stage retirement",
    expect_texts=["archive.final_report_retired", "deprecated"],
    llm_label="LLM retirement notice"))
