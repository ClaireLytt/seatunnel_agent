"""Browser tests for the React /partitionplan page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_partitionplan_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.partition_plan.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "partitionplan_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.partition_plan.api:router",
    "/partitionplan",
    env_var="PARTITIONPLAN_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Partition Plan", run_button="Plan partitions",
    expect_texts=["PARTITIONED BY (order_date)", "canonical key"],
    llm_label="LLM plan review"))
