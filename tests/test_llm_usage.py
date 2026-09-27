"""Tests for the cross-agent LLM usage log."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from seatunnel_agent import llm_usage


@pytest.fixture()
def usage_file(tmp_path, monkeypatch):
    path = tmp_path / "llm_usage.jsonl"
    monkeypatch.setenv("LLM_USAGE_PATH", str(path))
    monkeypatch.delenv("LLM_USAGE_LOG", raising=False)
    return path


def test_record_and_summarize(usage_file):
    llm_usage.record("openai", "kimi-k2", {"input": 100, "output": 20})
    llm_usage.record("openai", "kimi-k2", {"input": 50, "output": 10})
    llm_usage.record("anthropic", "claude-opus-5", {"input": 7, "output": 3})
    s = llm_usage.summarize()
    assert s["total"] == {"calls": 3, "input": 157, "output": 33}
    assert s["by_model"]["kimi-k2"] == {"calls": 2, "input": 150, "output": 30}
    assert len(s["by_day"]) == 1


def test_disabled_by_env(usage_file, monkeypatch):
    monkeypatch.setenv("LLM_USAGE_LOG", "0")
    llm_usage.record("openai", "m", {"input": 1, "output": 1})
    assert not usage_file.exists()


def test_missing_usage_and_file(usage_file):
    llm_usage.record("openai", "m", None)
    assert llm_usage.summarize()["total"]["calls"] == 1
    usage_file.unlink()
    assert llm_usage.summarize()["total"]["calls"] == 0


def test_old_records_excluded(usage_file):
    old = (datetime.now(timezone.utc) - timedelta(days=40)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    usage_file.write_text(
        json.dumps({"ts": old, "model": "m", "input": 5, "output": 5}) + "\n"
        + "not json\n", encoding="utf-8")
    llm_usage.record("openai", "m", {"input": 1, "output": 2})
    s = llm_usage.summarize(days=30)
    assert s["total"] == {"calls": 1, "input": 1, "output": 2}


def test_format_markdown(usage_file):
    assert "No LLM calls" in llm_usage.format_markdown("en")
    llm_usage.record("openai", "kimi-k2", {"input": 1000, "output": 200})
    md_zh = llm_usage.format_markdown("zh")
    assert "kimi-k2" in md_zh and "1,000" in md_zh
    assert "Last 30 days" in llm_usage.format_markdown("en")


def test_size_cap_trims_oldest_half(usage_file, monkeypatch):
    monkeypatch.setattr(llm_usage, "_MAX_LOG_BYTES", 200)
    for i in range(20):
        llm_usage.record("openai", f"m{i}", {"input": 1, "output": 1})
    lines = usage_file.read_text(encoding="utf-8").splitlines()
    assert 0 < len(lines) < 20
    assert "m19" in lines[-1]
