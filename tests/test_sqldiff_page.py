"""Browser tests for the React /sqldiff page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_sqldiff_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.sql_diff.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "sqldiff_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.sql_diff.api:router", "/sqldiff",
    env_var="SQLDIFF_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="SQL Diff", run_button="Compare",
    expect_texts=['order_cnt', 'dim.users'],
    llm_label="LLM change review"))
