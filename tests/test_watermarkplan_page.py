"""Browser tests for the React /watermarkplan page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_watermarkplan_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.watermark_plan.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "watermarkplan_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.watermark_plan.api:router",
    "/watermarkplan",
    env_var="WATERMARKPLAN_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Watermark Plan", run_button="Plan watermark",
    expect_texts=["INTERVAL '39' SECOND", "WM002"],
    llm_label="LLM watermark review"))
