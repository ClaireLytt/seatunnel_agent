"""Browser tests for the React /compactplan page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_compactplan_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.compact_plan.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "compactplan_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.compact_plan.api:router",
    "/compactplan",
    env_var="COMPACTPLAN_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Compaction Plan", run_button="Plan compaction",
    expect_texts=["CP002", "ods.click_log"],
    llm_label="LLM compaction review"))
