"""Tests for the data-comparison per-session connection registry."""

from __future__ import annotations

import threading

from seatunnel_agent.agents.data.data_comparison.registry import (
    ConnectionRegistry,
    SessionState,
    get_registry,
)


class TestSessionState:
    def test_default_fields(self):
        s = SessionState(session_id="x")
        assert s.session_id == "x"
        assert s.executor_a is None
        assert s.executor_b is None
        assert s.tables_a == []
        assert s.tables_b == []
        assert s.last_report is None
        assert s.schedule_timer is None
        assert s.schedule_active is False
        assert s.schedule_last_run is None
        assert s.schedule_last_error is None

    def test_tables_lists_not_shared_between_sessions(self):
        a = SessionState(session_id="a")
        b = SessionState(session_id="b")
        a.tables_a.append("orders")
        assert b.tables_a == []

    def test_has_own_lock(self):
        a = SessionState(session_id="a")
        b = SessionState(session_id="b")
        assert a.lock is not b.lock
        with a.lock:
            pass  # usable as a context manager


class TestConnectionRegistry:
    def test_create_returns_session_with_unique_id(self):
        reg = ConnectionRegistry()
        s1 = reg.create()
        s2 = reg.create()
        assert s1.session_id != s2.session_id

    def test_get_returns_same_object(self):
        reg = ConnectionRegistry()
        s = reg.create()
        assert reg.get(s.session_id) is s

    def test_get_unknown_returns_none(self):
        reg = ConnectionRegistry()
        assert reg.get("nope") is None

    def test_sessions_are_isolated(self):
        reg = ConnectionRegistry()
        s1 = reg.create()
        s2 = reg.create()
        s1.executor_a = object()
        s1.tables_a = ["t1"]
        assert s2.executor_a is None
        assert s2.tables_a == []

    def test_remove(self):
        reg = ConnectionRegistry()
        s = reg.create()
        reg.remove(s.session_id)
        assert reg.get(s.session_id) is None

    def test_remove_unknown_is_noop(self):
        ConnectionRegistry().remove("nope")

    def test_thread_safety_smoke(self):
        reg = ConnectionRegistry()
        ids: list[str] = []
        errors: list[BaseException] = []
        lock = threading.Lock()

        def worker():
            try:
                for _ in range(50):
                    s = reg.create()
                    assert reg.get(s.session_id) is s
                    with lock:
                        ids.append(s.session_id)
                    reg.remove(s.session_id)
                    assert reg.get(s.session_id) is None
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(set(ids)) == 8 * 50


def test_get_registry_singleton():
    assert get_registry() is get_registry()
    assert isinstance(get_registry(), ConnectionRegistry)
