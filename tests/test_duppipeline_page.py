"""Browser tests for the React /duppipeline page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_duppipeline_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.dup_pipeline.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "duppipeline_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.dup_pipeline.api:router", "/duppipeline",
    env_var="DUPPIPELINE_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Dup Pipelines", run_button="Detect duplicates",
    expect_texts=['DP001', 'dws.order_summary_bi'],
    llm_label="LLM consolidation plan"))
