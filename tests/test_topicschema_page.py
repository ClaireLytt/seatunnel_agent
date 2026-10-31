"""Browser tests for the React /topicschema page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_topicschema_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.topic_schema.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "topicschema_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.topic_schema.api:router",
    "/topicschema",
    env_var="TOPICSCHEMA_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Topic Schema Diff", run_button="Check compatibility",
    expect_texts=["INCOMPATIBLE", "status"],
    llm_label="LLM rollout note"))
