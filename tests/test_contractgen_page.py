"""Browser tests for the React /contractgen page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_contractgen_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.contract_gen.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "contractgen_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.contract_gen.api:router", "/contractgen",
    env_var="CONTRACTGEN_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Contract Draft", run_button="Draft contract",
    expect_texts=['require_comments', 'stg.clickstream_raw'],
    llm_label="LLM tightening suggestions"))
