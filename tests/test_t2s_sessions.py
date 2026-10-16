"""SessionManager unit seams the REST surface cannot reach (#100).

Everything reachable over HTTP is specified by the existing 14 protocol
tests, which must pass unchanged.
"""

from __future__ import annotations

from seatunnel_agent.agents.data.text2sql.sessions import SessionEntry, SessionManager


class _A:
    pass


def test_lru_evicts_oldest():
    m = SessionManager(max_size=2)
    s1 = m.create(_A(), connect=None)
    s2 = m.create(_A(), connect=None)
    s3 = m.create(_A(), connect=None)
    assert m.get(s1) is None  # evicted
    assert isinstance(m.get(s2), SessionEntry)
    assert isinstance(m.get(s3), SessionEntry)


def test_get_touch_refreshes_lru_order():
    m = SessionManager(max_size=2)
    s1 = m.create(_A(), connect=None)
    s2 = m.create(_A(), connect=None)
    m.get(s1)  # touch: s2 becomes oldest
    m.create(_A(), connect=None)
    assert m.get(s1) is not None
    assert m.get(s2) is None


def test_stop_on_idle_session_returns_false():
    m = SessionManager()
    sid = m.create(_A(), connect=None)
    assert m.stop(sid) is False  # no active stream to stop


def test_attach_stream_rejects_second_and_releases_on_finish():
    m = SessionManager()
    sid = m.create(_A(), connect=None)
    q = m.attach_stream(sid)
    assert q is not None
    assert m.attach_stream(sid) is None  # busy
    assert m.stop(sid) is True  # injects terminal event
    item = q.get_nowait()
    assert item[0] == "final_answer" and item[1].get("stopped") is True
    m.finish_stream(sid, q)
    assert m.attach_stream(sid) is not None  # free again


def test_replace_agent_on_missing_session_returns_none():
    m = SessionManager(max_size=1)
    sid = m.create(_A(), connect="c")
    m.create(_A(), connect=None)  # evicts sid
    assert m.replace_agent(sid, _A()) is None  # atomic, no assert/raise


def test_put_legacy_wraps_in_entry_shape():
    m = SessionManager()
    a = _A()
    m.put_legacy("client-key", a)
    entry = m.get("client-key")
    assert isinstance(entry, SessionEntry)
    assert entry.agent is a and entry.connect is None
