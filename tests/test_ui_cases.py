# -*- coding: utf-8 -*-
"""Per-case pytest bridge for the UI suite.

Unlike test_ui_smoke.py (one node for the whole smoke run), every YAML case
becomes its own pytest node, so CI shows exactly which case failed and the
usual pytest tooling works case-by-case:

    pytest -m uitest tests/test_ui_cases.py                 # smoke set
    UITEST_SUITE=full pytest -m uitest tests/test_ui_cases.py
    UITEST_CASES="IMP1 TRP7" pytest -m uitest tests/test_ui_cases.py
    pytest -m uitest tests/test_ui_cases.py -k "SCR"        # pytest filters
    pytest -m uitest tests/test_ui_cases.py --lf            # rerun failures

The app and browser boot once per session (same cost as the runner); each
node then drives one case. Always LLM-free — ai cases report SKIP.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.uitest

_PORT = int(os.getenv("UITEST_PORT", "7916"))


def _collect():
    from seatunnel_agent.ui_testing.loader import filter_cases, load_cases

    suite = os.getenv("UITEST_SUITE", "smoke")
    ids = os.getenv("UITEST_CASES", "").split() or None
    cases = filter_cases(load_cases(), suite, ids)
    return [c for c in cases if "manual" not in c.tags]


CASES = _collect()


@pytest.fixture(scope="session")
def ui_env(tmp_path_factory):
    from playwright.sync_api import sync_playwright

    from seatunnel_agent.ui_testing.env import AppUnderTest
    from seatunnel_agent.ui_testing.page import DCPage

    shots = tmp_path_factory.mktemp("shots")
    with AppUnderTest(port=_PORT, log_dir=shots.parent) as app:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1600, "height": 900})
            page.set_default_timeout(10_000)
            yield DCPage(page, app.base_url), shots, app
            browser.close()


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_ui_case(case, ui_env):
    from seatunnel_agent.ui_testing.runner import _skip_reason, run_case

    dc, shots, app = ui_env
    reason = _skip_reason(case, no_llm=True)
    if reason:
        pytest.skip(reason)
    cr = run_case(case, dc, llm=None, shots_dir=Path(shots),
                  app_log_tail_fn=app.log_tail)
    if cr.verdict == "SKIP":
        pytest.skip(cr.reason or "skipped by the runner")
    detail = "\n".join(
        f"  [FAIL] {s.desc}: {s.detail}"
        for s in [*cr.steps, *cr.asserts] if not s.ok) or cr.reason
    assert cr.verdict == "PASS", f"{case.id} {cr.verdict}: {detail}"
