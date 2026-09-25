# -*- coding: utf-8 -*-
"""pytest bridge for the UI smoke suite.

Deselected by default (needs a browser and ~3 minutes); run explicitly:

    pytest -m uitest tests/test_ui_smoke.py
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.uitest


@pytest.mark.uitest
def test_ui_smoke():
    from seatunnel_agent.ui_testing.report import write_html, write_json
    from seatunnel_agent.ui_testing.runner import run_suite

    rr, run_dir = run_suite(suite="smoke", no_llm=True)
    write_json(rr, run_dir)
    write_html(rr, run_dir)
    bad = [c for c in rr.cases if c.verdict in ("FAIL", "ERROR")]
    assert not bad, "\n".join(
        f"{c.case_id}: {c.reason} (report: {run_dir / 'report.html'})"
        for c in bad)
