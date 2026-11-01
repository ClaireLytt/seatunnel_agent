"""Browser tests for the React /timezoneaudit page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_timezoneaudit_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.timezone_audit.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "timezoneaudit_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.timezone_audit.api:router",
    "/timezoneaudit",
    env_var="TIMEZONEAUDIT_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Timezone Audit", run_button="Audit timestamps",
    expect_texts=["TZ001", "event_ts"],
    llm_label="LLM normalization note"))
