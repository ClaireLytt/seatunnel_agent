"""Browser tests for the React /ddlevolve page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_ddlevolve_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.ddl_evolve.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "ddlevolve_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.ddl_evolve.api:router", "/ddlevolve",
    env_var="DDLEVOLVE_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="DDL Migration", run_button="Build migration",
    expect_texts=['ADD COLUMNS', 'age BIGINT'],
    llm_label="LLM rollout advice"))
