"""Browser tests for the React /avro2ddl page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_avro2ddl_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.avro2ddl.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "avro2ddl_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.avro2ddl.api:router",
    "/avro2ddl",
    env_var="AVRO2DDL_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="Avro to DDL", run_button="Generate DDL",
    expect_texts=["DECIMAL(16,2)", "shop.Order"],
    llm_label="LLM landing review"))
