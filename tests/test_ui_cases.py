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
    pytest -m uitest tests/test_ui_cases.py -n 4            # xdist parallel

The app and browser boot once per session (same cost as the runner); each
node then drives one case. Always LLM-free — ai cases report SKIP.

Under pytest-xdist every worker boots its own app+browser on its own port
(base UITEST_PORT + worker index), so cases run truly in parallel. Cases
are independent by design (fresh page load each), with one exception the
scheduler must respect: SET6-SET8 share a profile-lifecycle chain — use
``-n 4 --dist loadgroup`` (they carry the same xdist_group) to keep them
on one worker, in order.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.uitest

# gw0/gw1/... under xdist; each worker gets its own app on its own port
_WORKER = os.getenv("PYTEST_XDIST_WORKER", "")
_OFFSET = int(_WORKER[2:]) if _WORKER.startswith("gw") and _WORKER[2:].isdigit() else 0
_PORT = int(os.getenv("UITEST_PORT", "7916")) + _OFFSET * 3


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


# Case chains that mutate/clean shared state: pin each chain to one xdist
# worker (in file order) via --dist loadgroup; everything else is free.
_CHAIN_GROUPS = {
    "SET6": "settings-profile", "SET7": "settings-profile",
    "SET8": "settings-profile",
    "SET9": "settings-conns", "SET10": "settings-conns",
}


@pytest.mark.parametrize(
    "case",
    [pytest.param(c, marks=pytest.mark.xdist_group(_CHAIN_GROUPS[c.id]))
     if c.id in _CHAIN_GROUPS else c for c in CASES],
    ids=[c.id for c in CASES])
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
