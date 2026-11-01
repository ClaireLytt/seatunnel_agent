"""Browser tests for the React /seatunnelgen page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_seatunnelgen_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.seatunnel_gen.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "seatunnelgen_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.seatunnel_gen.api:router", "/seatunnelgen",
    env_var="SEATUNNELGEN_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Job Draft", run_button="Draft job",
    expect_texts=['STREAMING', 'fenodes'],
    llm_label="LLM pre-run review"))
