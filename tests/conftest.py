"""Shared test fixtures."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Redirect the text2sql example store OUT of the repo before any test module
# imports examples.py (its default path is read at import time). Without this,
# every full pytest run rewrites config/t2s_examples.json (id/timestamp churn)
# and dirties the working tree — see docs/pitfalls.md 2026-10-17/18.
_T2S_TMP = Path(tempfile.mkdtemp(prefix="t2s_examples_")) / "t2s_examples.json"
os.environ.setdefault("T2S_EXAMPLES_PATH", str(_T2S_TMP))


# ── shared Playwright helpers (importable: from tests.conftest import …) ──


def download_text(download) -> str:
    """Save a Playwright download and read it back as text."""
    return Path(download.path()).read_text(encoding="utf-8")


def labeled_select(page, label: str):
    """Locator for the <select> that directly follows the visible label
    text. The React pages render ``<label>…</label><select>`` without
    id/for hooks, so anchor on the label instead of positional nth()."""
    return page.get_by_text(label, exact=True).locator(
        "xpath=following-sibling::select")


def assert_dialect_switch(page, *, dialect: str, run, report,
                          contains: str | None = None,
                          timeout: int = 15000, select=None) -> None:
    """Shared ticket-05 dialect-switch body: select a non-default dialect,
    assert the value stuck, run the page's action (``run()`` does the
    fills/clicks and any page-specific assertions), then assert the report
    rendered with no traceback."""
    from playwright.sync_api import expect

    sel = select if select is not None else page.locator("select").first
    sel.select_option(dialect)
    expect(sel).to_have_value(dialect)
    run()
    expect(report).to_be_visible(timeout=timeout)
    if contains is not None:
        expect(report).to_contain_text(contains)
    expect(page.locator("body")).not_to_contain_text("Traceback")


@pytest.fixture(autouse=True)
def _no_llm_usage_log(monkeypatch):
    """Tests must not append to the real logs/llm_usage.jsonl.

    test_llm_usage re-enables recording by deleting the var and pointing
    LLM_USAGE_PATH at a tmp file."""
    monkeypatch.setenv("LLM_USAGE_LOG", "0")
    monkeypatch.setenv("PROMPT_LAB_LOG", "0")
    monkeypatch.setenv("LLM_EVAL_LOG", "0")
    monkeypatch.setenv("ORCH_CHAT_LOG", "0")
