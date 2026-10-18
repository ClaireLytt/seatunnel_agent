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


@pytest.fixture(autouse=True)
def _no_llm_usage_log(monkeypatch):
    """Tests must not append to the real logs/llm_usage.jsonl.

    test_llm_usage re-enables recording by deleting the var and pointing
    LLM_USAGE_PATH at a tmp file."""
    monkeypatch.setenv("LLM_USAGE_LOG", "0")
    monkeypatch.setenv("PROMPT_LAB_LOG", "0")
    monkeypatch.setenv("LLM_EVAL_LOG", "0")
    monkeypatch.setenv("ORCH_CHAT_LOG", "0")
