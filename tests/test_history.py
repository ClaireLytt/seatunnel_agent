"""Tests for chat history persistence."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from seatunnel_agent.history import (
    Session,
    delete_session,
    extract_title,
    list_sessions,
    load_session,
    new_session_id,
    rename_session,
    save_session,
)


@pytest.fixture(autouse=True)
def _use_tmp_dir(tmp_path: Path):
    with patch("seatunnel_agent.history.HISTORY_DIR", tmp_path):
        yield tmp_path


def _make_session(**overrides) -> Session:
    defaults = dict(
        session_id=new_session_id(),
        title="Test session",
        created_at="2026-09-11T12:00:00",
        updated_at="2026-09-11T12:00:00",
        chat_messages=[{"role": "user", "content": "hello"}],
        agent_messages=[{"role": "user", "content": "hello"}],
    )
    defaults.update(overrides)
    return Session(**defaults)


class TestSaveAndLoad:
    def test_roundtrip(self):
        s = _make_session()
        save_session(s)
        loaded = load_session(s.session_id)
        assert loaded is not None
        assert loaded.session_id == s.session_id
        assert loaded.title == s.title
        assert loaded.chat_messages == s.chat_messages
        assert loaded.agent_messages == s.agent_messages

    def test_save_updates_timestamp(self):
        s = _make_session(updated_at="old")
        save_session(s)
        loaded = load_session(s.session_id)
        assert loaded.updated_at != "old"

    def test_load_nonexistent_returns_none(self):
        assert load_session("does-not-exist") is None

    def test_load_corrupt_json_returns_none(self, _use_tmp_dir):
        bad = _use_tmp_dir / "corrupt.json"
        bad.write_text("{invalid json", encoding="utf-8")
        assert load_session("corrupt") is None


class TestDelete:
    def test_delete_existing(self):
        s = _make_session()
        save_session(s)
        delete_session(s.session_id)
        assert load_session(s.session_id) is None

    def test_delete_nonexistent_is_noop(self):
        delete_session("nonexistent")


class TestRename:
    def test_rename_existing(self):
        s = _make_session()
        save_session(s)
        assert rename_session(s.session_id, "New Title")
        loaded = load_session(s.session_id)
        assert loaded.title == "New Title"

    def test_rename_nonexistent(self):
        assert rename_session("nope", "Title") is False

    def test_rename_empty_string_keeps_original(self):
        s = _make_session(title="Original")
        save_session(s)
        assert rename_session(s.session_id, "   ")
        loaded = load_session(s.session_id)
        assert loaded.title == "Original"

    def test_rename_strips_whitespace(self):
        s = _make_session()
        save_session(s)
        rename_session(s.session_id, "  Trimmed  ")
        loaded = load_session(s.session_id)
        assert loaded.title == "Trimmed"


class TestListSessions:
    def test_empty_dir(self):
        assert list_sessions() == []

    def test_sorted_by_updated_desc(self, _use_tmp_dir):
        import json as _json
        for sid, title, ts in [
            ("aaa", "first", "2026-01-01T00:00:00"),
            ("bbb", "second", "2026-06-01T00:00:00"),
        ]:
            (_use_tmp_dir / f"{sid}.json").write_text(
                _json.dumps({
                    "session_id": sid, "title": title,
                    "created_at": ts, "updated_at": ts,
                    "chat_messages": [], "agent_messages": [],
                }),
                encoding="utf-8",
            )
        result = list_sessions()
        assert len(result) == 2
        assert result[0]["title"] == "second"
        assert result[1]["title"] == "first"

    def test_skips_corrupt_files(self, _use_tmp_dir):
        s = _make_session()
        save_session(s)
        bad = _use_tmp_dir / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        result = list_sessions()
        assert len(result) == 1


class TestExtractTitle:
    def test_first_user_message(self):
        msgs = [
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "Generate fake data"},
        ]
        assert extract_title(msgs) == "Generate fake data"

    def test_truncation(self):
        long = "x" * 100
        title = extract_title([{"role": "user", "content": long}])
        assert len(title) == 33
        assert title.endswith("...")

    def test_no_user_message(self):
        assert extract_title([{"role": "assistant", "content": "hi"}]) == "Untitled"

    def test_empty_list(self):
        assert extract_title([]) == "Untitled"


class TestNewSessionId:
    def test_length(self):
        sid = new_session_id()
        assert len(sid) == 12

    def test_unique(self):
        ids = {new_session_id() for _ in range(100)}
        assert len(ids) == 100
