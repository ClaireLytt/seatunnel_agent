"""Browser tests for the React /fieldusage page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_fieldusage_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.field_usage.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "fieldusage_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.field_usage.api:router",
    "/fieldusage",
    env_var="FIELDUSAGE_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Field Usage", run_button="Analyze usage",
    expect_texts=["FU001", "tmp.old_backup"],
    llm_label="LLM disposition advice"))
