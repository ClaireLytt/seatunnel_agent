"""Per-session state isolation (SessionScopedDict) — regression for the
cross-session state leak where one browser session's Connect overwrote
another session's agent/db_config/session_id."""

from __future__ import annotations

import inspect
from contextlib import contextmanager
from types import SimpleNamespace

from seatunnel_agent.common import session_scope
from seatunnel_agent.common.session_scope import SessionScopedDict


@contextmanager
def _gradio_session(session_hash: str):
    """Simulate Gradio's per-event request contextvar."""
    from gradio.context import LocalContext

    token = LocalContext.request.set(SimpleNamespace(session_hash=session_hash))
    try:
        yield
    finally:
        LocalContext.request.reset(token)


def _fresh():
    return {"agent": None, "db_config": None, "session_id": None}


def test_two_sessions_do_not_overwrite_each_other():
    holder = SessionScopedDict(_fresh)

    with _gradio_session("session-a"):
        holder["agent"] = "agent-A"
        holder["db_config"] = {"host": "db-a"}
        holder["session_id"] = "sid-a"

    # User B connects with a different database.
    with _gradio_session("session-b"):
        assert holder["agent"] is None  # B starts from a fresh bucket
        holder["agent"] = "agent-B"
        holder["db_config"] = {"host": "db-b"}
        holder["session_id"] = "sid-b"

    # User A's state is untouched by B's connect.
    with _gradio_session("session-a"):
        assert holder["agent"] == "agent-A"
        assert holder["db_config"] == {"host": "db-a"}
        assert holder["session_id"] == "sid-a"


def test_mapping_protocol_within_a_session():
    holder = SessionScopedDict(_fresh)
    with _gradio_session("s1"):
        assert holder.get("missing") is None
        holder["x"] = 1
        assert "x" in holder
        assert holder.pop("x") == 1
        assert holder.pop("x", "fallback") == "fallback"
        assert len(holder) == len(_fresh())


def test_no_request_falls_back_to_default_bucket():
    holder = SessionScopedDict(_fresh)
    holder["agent"] = "cli-agent"
    assert holder["agent"] == "cli-agent"
    with _gradio_session("browser"):
        assert holder["agent"] is None  # browser session is isolated from it


def test_resolve_pins_bucket_for_background_threads():
    holder = SessionScopedDict(_fresh)
    with _gradio_session("s1"):
        bucket = holder.resolve()
    # Outside the request context (as in a spawned thread), the pinned
    # bucket still writes into session s1.
    bucket["agent"] = "warmed-up"
    with _gradio_session("s1"):
        assert holder["agent"] == "warmed-up"


def test_bucket_count_is_lru_capped():
    holder = SessionScopedDict(_fresh)
    cap = session_scope._MAX_SESSIONS
    for i in range(cap + 10):
        with _gradio_session(f"s{i}"):
            holder["agent"] = i
    assert len(holder._buckets) == cap
    with _gradio_session("s0"):  # evicted → fresh bucket, not someone else's
        assert holder["agent"] is None


def test_ui_pages_use_session_scoped_holders():
    """Guard: the two chat pages must keep per-session (not shared) holders."""
    from seatunnel_agent.agents.data.seatunnel import ui as st_ui
    from seatunnel_agent.agents.data.text2sql import ui as t2s_ui

    assert "SessionScopedDict(" in inspect.getsource(t2s_ui.render_text2sql_page)
    assert inspect.getsource(st_ui._render_seatunnel_page).count("SessionScopedDict(") == 3
