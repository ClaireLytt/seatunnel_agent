"""Browser tests for the React /retention page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_retention_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.retention_policy.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "retention_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.retention_policy.api:router",
    "/retention",
    env_var="RETENTION_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Retention Advice", run_button="Advise retention",
    expect_texts=["RP001", "ods.click_log"],
    llm_label="LLM cleanup proposal"))
