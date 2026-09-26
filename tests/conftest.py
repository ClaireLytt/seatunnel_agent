"""Shared test fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_llm_usage_log(monkeypatch):
    """Tests must not append to the real logs/llm_usage.jsonl.

    test_llm_usage re-enables recording by deleting the var and pointing
    LLM_USAGE_PATH at a tmp file."""
    monkeypatch.setenv("LLM_USAGE_LOG", "0")
