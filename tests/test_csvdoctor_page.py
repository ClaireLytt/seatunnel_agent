"""Browser tests for the React /csvdoctor page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_csvdoctor_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.csv_doctor.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "csvdoctor_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.csv_doctor.api:router",
    "/csvdoctor",
    env_var="CSVDOCTOR_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="CSV Doctor", run_button="Diagnose file",
    expect_texts=["CD005", "name_2"],
    llm_label="LLM incident note"))
