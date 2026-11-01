"""Browser tests for the React /mockdata page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_mockdata_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.mock_data.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "mockdata_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.mock_data.api:router", "/mockdata",
    env_var="MOCKDATA_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Mock Data", run_button="Generate rows",
    expect_texts=['synthesized phone', 'Download CSV'],
    llm_label="LLM dataset note"))
