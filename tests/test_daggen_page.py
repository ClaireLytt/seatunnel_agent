"""Browser tests for the React /daggen page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_daggen_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.dag_gen.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "daggen_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.dag_gen.api:router", "/daggen",
    env_var="DAGGEN_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="DAG Draft", run_button="Draft DAG",
    expect_texts=["ads_final_report", "BashOperator"],
    llm_label="LLM pre-deploy review"))
