"""Browser tests for the React /incidentreview page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_incidentreview_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.incident_review.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "incidentreview_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.incident_review.api:router",
    "/incidentreview",
    env_var="INCIDENTREVIEW_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Incident Review", run_button="Review incident",
    expect_texts=["MTTR", "IR003"],
    llm_label="LLM postmortem draft"))
