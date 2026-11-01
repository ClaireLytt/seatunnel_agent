"""Browser tests for the React /joinaudit page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_joinaudit_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.join_audit.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "joinaudit_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.join_audit.api:router", "/joinaudit",
    env_var="JOINAUDIT_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Join Audit", run_button="Audit join",
    expect_texts=['JA001', 'many-to-many'],
    llm_label="LLM join review"))
