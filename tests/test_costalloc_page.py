"""Browser tests for the React /costalloc page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_costalloc_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.cost_allocation.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "costalloc_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.cost_allocation.api:router",
    "/costalloc",
    env_var="COSTALLOC_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Cost Allocation", run_button="Allocate costs",
    expect_texts=["CA001", "tmp.old_backup"],
    llm_label="LLM billing note"))
