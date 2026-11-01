"""Browser tests for the React /coveragemap page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_coveragemap_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.coverage_map.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "coveragemap_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.coverage_map.api:router",
    "/coveragemap",
    env_var="COVERAGEMAP_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Coverage Map", run_button="Map coverage",
    expect_texts=["CM001", "dws.orders_daily"],
    llm_label="LLM gap-closing plan"))
