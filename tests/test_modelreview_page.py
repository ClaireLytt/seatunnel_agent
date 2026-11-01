"""Browser tests for the React /modelreview page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_modelreview_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.model_review.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "modelreview_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.model_review.api:router", "/modelreview",
    env_var="MODELREVIEW_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Model Review", run_button="Review model",
    expect_texts=['MR001', 'dim.users'],
    llm_label="LLM refactoring advice"))
