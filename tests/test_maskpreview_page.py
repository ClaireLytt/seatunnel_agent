"""Browser tests for the React /maskpreview page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_maskpreview_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.mask_preview.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "maskpreview_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.mask_preview.api:router", "/maskpreview",
    env_var="MASKPREVIEW_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Mask Preview", run_button="Preview masks",
    expect_texts=['138****0001', 'id_card'],
    llm_label="LLM policy note"))
