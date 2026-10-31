"""Browser tests for the React /dqrulegen page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_dqrulegen_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.dq_rulegen.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "dqrulegen_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.dq_rulegen.api:router", "/dqrulegen",
    env_var="DQRULEGEN_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="DQC Rule Draft", run_button="Draft rules",
    expect_texts=['enum_domain', 'max_change_pct'],
    llm_label="LLM tightening suggestions"))
