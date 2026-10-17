"""REST API for the SeaTunnel Pipeline Builder React page — FastAPI router.

Mounted unconditionally on the served FastAPI instance after hub launch
(see seatunnel_agent.hub.ui), like the uitest / sql_review routers.

Endpoints (sessions persistence/export land in later tickets):
  GET  /api/seatunnel/meta      — static page metadata: modes, templates
  POST /api/seatunnel/chat      — one chat turn as SSE (drives SeaTunnelAgent)
  POST /api/seatunnel/chat/stop — interrupt the running turn
  POST /api/seatunnel/upload    — attach a config file (saved under configs/)
  POST /api/seatunnel/demo      — scripted demo run streamed as chat SSE
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from seatunnel_agent.agents.data.seatunnel.agent import SeaTunnelAgent
from seatunnel_agent.common.config import load_settings

router = APIRouter(prefix="/api/seatunnel", tags=["seatunnel"])

# the four legacy agent modes; labels mirror the Gradio page's i18n dict
# (seatunnel.ui._I18N mode_* keys) so the React page loses no wording
_MODES: list[dict[str, str]] = [
    {"key": "nl", "en": "Natural Language", "zh": "自然语言描述"},
    {"key": "run", "en": "Run Config", "zh": "运行配置文件"},
    {"key": "validate", "en": "Validate Config", "zh": "验证配置"},
    {"key": "diagnose", "en": "Diagnose Log", "zh": "诊断日志"},
]


@router.get("/meta")
def get_meta() -> dict[str, Any]:
    """Static page metadata: agent modes and pipeline templates."""
    from seatunnel_agent.agents.data.seatunnel.templates import TEMPLATES

    return {
        "modes": _MODES,
        "templates": [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "parameters": t.parameters,
            }
            for t in TEMPLATES
        ],
        "config_placeholder": "examples/fake_to_console.conf",
    }


# ── Chat SSE ─────────────────────────────────────────────────────────

# mirrors the legacy Gradio page's _I18N strings (ui.py) 1:1; the page
# itself retires in a later ticket, so the API keeps its own copy
_MSG: dict[str, dict[str, str]] = {
    "no_settings": {
        "en": "Settings not loaded. Click **Connect** first and make sure "
              "`.env` is configured.",
        "zh": "未加载配置。请先点击 **连接**，确保 `.env` 已配置。",
    },
    "stopped": {
        "en": "Agent stopped by user.",
        "zh": "已被用户中断。",
    },
}


@dataclass
class _Conversation:
    """In-memory state for one page-session conversation."""

    agent: Any = None
    queue: queue.Queue[tuple[str, dict[str, Any]] | None] | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    # accumulated rendered chat (user + legacy-rendered assistant messages);
    # what _persist_session writes to the history file, legacy ui.py parity
    messages: list[dict[str, str]] = field(default_factory=list)


def _persist_session(cid: str, conv: _Conversation) -> None:
    """Save the conversation to history like legacy ui.py _save_current_session."""
    from seatunnel_agent.common import history

    if not conv.messages:
        return
    try:
        existing = history.load_session(cid)
        created = existing.created_at if existing else history.now_iso()
        agent = conv.agent
        history.save_session(history.Session(
            session_id=cid,
            title=history.extract_title(conv.messages),
            created_at=created,
            updated_at=history.now_iso(),
            chat_messages=list(conv.messages),
            agent_messages=list(getattr(agent, "messages", None) or []),
            agent_context=dict(getattr(agent, "context", None) or {}),
        ))
    except Exception:  # pragma: no cover - persistence must not kill the stream
        import logging

        logging.getLogger(__name__).warning(
            "failed to persist seatunnel session %s", cid, exc_info=True)


_CONVERSATIONS: dict[str, _Conversation] = {}


class ChatRequest(BaseModel):
    message: str = ""
    mode: str = "nl"  # nl | run | validate | diagnose (meta mode keys)
    config_path: str = ""
    conversation_id: str | None = None
    lang: str = "en"


class StopRequest(BaseModel):
    conversation_id: str
    lang: str = "en"


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _render_event(ev: dict[str, Any], start_time: float) -> str | None:
    """Render one agent event to the legacy chat markdown (ui.py renderer)."""
    from seatunnel_agent.agents.data.seatunnel.ui import _format_events_as_chat

    msgs = _format_events_as_chat([ev], start_time)
    return msgs[0]["content"] if msgs else None


@router.post("/chat")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    """Stream one chat turn as SSE, driving the SeaTunnelAgent unchanged.

    Frames: conversation (id), delta (streamed text), event (kind +
    pre-rendered legacy markdown), final (elapsed [, error, stopped]).
    """
    if not req.message.strip() and not req.config_path.strip():
        raise HTTPException(status_code=400, detail="empty message")

    cid = req.conversation_id or uuid.uuid4().hex[:12]
    conv = _CONVERSATIONS.setdefault(cid, _Conversation())

    with conv.lock:
        if conv.queue is not None:
            raise HTTPException(status_code=409,
                                detail="a chat turn is already running")
        q: queue.Queue[tuple[str, dict[str, Any]] | None] = queue.Queue()
        conv.queue = q

    # settings come from Connect when available (with a stale-version reload,
    # legacy ui.py _handle_submit parity), else a direct load
    from seatunnel_agent.common import settings_store

    settings = CONNECTION.get("settings")
    if settings is not None and CONNECTION.get("version") != settings_store.get_version():
        try:
            settings = load_settings()
            CONNECTION["settings"] = settings
            CONNECTION["version"] = settings_store.get_version()
            conv.agent = None  # drop the cached agent so the new key/model applies
        except Exception:
            pass  # keep the old settings; the run itself surfaces errors

    is_first = conv.agent is None
    if is_first and settings is None:
        try:
            settings = load_settings()
        except Exception:
            conv.queue = None

            def no_settings_stream():
                yield _sse({"type": "conversation", "id": cid})
                yield _sse({"type": "event", "kind": "text",
                            "markdown": _MSG["no_settings"].get(
                                req.lang, _MSG["no_settings"]["en"])})
                yield _sse({"type": "final"})

            return StreamingResponse(no_settings_stream(),
                                     media_type="text/event-stream")

    def on_event(etype: str, data: dict[str, Any]) -> None:
        q.put((etype, data or {}))

    error_holder: dict[str, str] = {}
    msg = req.message.strip()
    cfg = req.config_path.strip()

    if is_first:
        agent = SeaTunnelAgent(settings, on_event=on_event)
        conv.agent = agent
    else:
        agent = conv.agent
        agent._on_event = on_event

    def work() -> None:
        try:
            if is_first:
                # mode dispatch mirrors ui.py _run_agent_streaming
                if req.mode == "run" and cfg:
                    agent.run_with_config(cfg)
                elif req.mode == "validate" and cfg:
                    agent.validate_only(cfg)
                elif req.mode == "diagnose" and cfg:
                    agent.diagnose_log(cfg)
                else:
                    agent.run(msg)
            else:
                agent.chat(msg)
        except Exception as e:
            error_holder["error"] = str(e)
            q.put(("final_answer", {"text": f"Error: {e}"}))

    threading.Thread(target=work, daemon=True).start()
    start_time = time.time()

    events_log: list[dict[str, Any]] = []

    def stream():
        try:
            yield _sse({"type": "conversation", "id": cid})
            while True:
                item = q.get()
                if item is None:
                    break
                etype, data = item
                events_log.append({"type": etype, **data})
                if etype == "text_delta":
                    yield _sse({"type": "delta", "text": data.get("text", "")})
                elif etype == "final_answer":
                    final: dict[str, Any] = {"type": "final",
                                             "elapsed": time.time() - start_time}
                    if error_holder.get("error"):
                        final["error"] = error_holder["error"]
                    if data.get("stopped"):
                        final["stopped"] = True
                    yield _sse(final)
                    break
                else:
                    markdown = _render_event({"type": etype, **data}, start_time)
                    if markdown is not None:
                        yield _sse({"type": "event", "kind": etype,
                                    "markdown": markdown})
        finally:
            with conv.lock:
                conv.queue = None
            if conv.agent is not None:
                conv.agent._on_event = None
            # persist the completed exchange (legacy _handle_submit parity)
            from seatunnel_agent.agents.data.seatunnel.ui import (
                _format_events_as_chat,
            )

            conv.messages.append({"role": "user", "content": req.message})
            conv.messages.extend(_format_events_as_chat(events_log, start_time))
            _persist_session(cid, conv)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/chat/stop")
def chat_stop(req: StopRequest) -> dict[str, Any]:
    """Interrupt the running turn; the partial reply stays in the stream."""
    conv = _CONVERSATIONS.get(req.conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="unknown conversation")
    if conv.agent is not None:
        conv.agent.stop_event.set()
    with conv.lock:
        q = conv.queue
    if q is not None:
        # mirrors ui.py _handle_stop: inject a final_answer so the stream
        # ends immediately, leaving the partial reply visible
        q.put(("final_answer",
               {"text": _MSG["stopped"].get(req.lang, _MSG["stopped"]["en"]),
                "stopped": True}))
    return {"stopped": True}


# ── Connect ──────────────────────────────────────────────────────────

# Connection state shared with the chat endpoints. Mirrors the
# legacy page's settings_holder: holds the loaded Settings plus the
# settings_store version seen at connect time, so a stale-settings reload can
# be detected before each run (legacy ui.py _handle_submit parity).
CONNECTION: dict[str, Any] = {"settings": None, "version": None}


def _warmup_llm(provider: str) -> None:
    """Pre-import the LLM SDK so the first chat doesn't pay the import cost."""
    try:
        if provider == "anthropic":
            import anthropic  # noqa: F401
        else:
            import openai  # noqa: F401
    except Exception:
        pass


@router.post("/connect")
def connect() -> dict[str, Any]:
    """Load settings and report the genuine connect result (success or failure)."""
    import threading

    from seatunnel_agent.common import config, settings_store

    try:
        settings = config.load_settings()
    except Exception as e:
        CONNECTION["settings"] = None
        CONNECTION["version"] = None
        return {"ok": False, "error": str(e)}

    CONNECTION["settings"] = settings
    CONNECTION["version"] = settings_store.get_version()
    threading.Thread(target=_warmup_llm, args=(settings.llm_provider,), daemon=True).start()
    return {"ok": True, "model": settings.model_name}


# ── Sessions ─────────────────────────────────────────────────────────
# Backed by seatunnel_agent.common.history — storage format unchanged
# (legacy parity with the Gradio page's session sidebar handlers).


class RenameRequest(BaseModel):
    title: str


@router.get("/sessions")
def sessions_list() -> dict[str, Any]:
    """List saved sessions, newest first (title / updated_at / msg_count)."""
    from seatunnel_agent.common import history

    return {"sessions": history.list_sessions()}


@router.get("/sessions/{session_id}")
def session_load(session_id: str) -> dict[str, Any]:
    """Load a session: return its chat messages and restore the agent state
    so follow-up chat turns continue that conversation (legacy _load_history)."""
    from seatunnel_agent.common import history

    session = history.load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session")

    conv = _CONVERSATIONS.setdefault(session_id, _Conversation())
    conv.messages = list(session.chat_messages)
    conv.agent = None
    if session.agent_messages:
        settings = CONNECTION.get("settings")
        if settings is not None:
            agent = SeaTunnelAgent(settings, on_event=None)
            agent.messages = list(session.agent_messages)
            if session.agent_context:
                agent.context = dict(session.agent_context)
            conv.agent = agent

    return {"id": session_id, "title": session.title,
            "messages": session.chat_messages}


@router.patch("/sessions/{session_id}")
def session_rename(session_id: str, req: RenameRequest) -> dict[str, Any]:
    from seatunnel_agent.common import history

    if not history.rename_session(session_id, req.title):
        raise HTTPException(status_code=404, detail="unknown session")
    return {"ok": True}


@router.delete("/sessions/{session_id}")
def session_delete(session_id: str) -> dict[str, Any]:
    from seatunnel_agent.common import history

    history.delete_session(session_id)
    _CONVERSATIONS.pop(session_id, None)
    return {"ok": True}

# ── Upload ───────────────────────────────────────────────────────────


@router.post("/upload")
async def upload_file(file: UploadFile) -> dict[str, str]:
    """Save an uploaded config into configs/ (legacy _handle_file_upload parity).

    The sanitized relative path is returned for the page to put into the
    config-path field, exactly as the Gradio UploadButton handler did.
    """
    import re
    from pathlib import Path

    safe_name = re.sub(r"[^\w.\-]", "_", file.filename or "upload.conf")
    dest_dir = Path("configs")
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / safe_name
    dest.write_bytes(await file.read())
    return {"path": str(dest)}


# ── Demo ─────────────────────────────────────────────────────────────


class DemoRequest(BaseModel):
    config_path: str = ""
    lang: str = "en"


@router.post("/demo")
def demo_stream(req: DemoRequest) -> StreamingResponse:
    """Stream the scripted demo over the same SSE frames as /chat.

    1:1 with legacy ui.py _run_demo: same _DEMO_STEPS scripts, real
    execute_tool calls against a fake Settings, UI_DEMO_STEP_DELAY pause
    between steps, demo config written to the temp dir when no real
    config path is given.
    """
    import os
    import tempfile

    from seatunnel_agent.agents.data.seatunnel.tools import execute_tool
    from seatunnel_agent.agents.data.seatunnel.ui import _DEMO_CONFIG, _DEMO_STEPS, _t
    from seatunnel_agent.common.config import Settings, env_float

    delay = env_float("UI_DEMO_STEP_DELAY", 0.35)
    fake_settings = Settings(
        api_key="demo", seatunnel_home=".", seatunnel_bin="", max_retries=3,
    )

    config_path = req.config_path.strip()
    has_config = bool(config_path) and os.path.isfile(config_path)
    key = "validate" if has_config else "general"
    steps = _DEMO_STEPS[key]

    if not has_config:
        config_path = os.path.join(tempfile.gettempdir(), "demo_fake_to_console.conf")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(_DEMO_CONFIG)

    def _tool_input(name: str) -> dict[str, Any]:
        if name == "write_config":
            return {"config_path": config_path, "content": _DEMO_CONFIG}
        if name in ("read_config", "validate_config"):
            return {"config_path": config_path}
        return {}

    cid = uuid.uuid4().hex[:12]
    start_time = time.time()

    def stream():
        yield _sse({"type": "conversation", "id": cid})
        for step in steps:
            t = step["type"]
            time.sleep(delay)

            if t == "final_answer":
                yield _sse({"type": "final", "elapsed": time.time() - start_time})
                break

            if t == "thinking":
                ev: dict[str, Any] = {"type": "thinking", "text": step["text"]}
            elif t == "tool_call":
                ev = {"type": "tool_call", "name": step["name"],
                      "input": _tool_input(step["name"])}
            elif t == "tool_result":
                result = execute_tool(step["name"], _tool_input(step["name"]),
                                      fake_settings)
                ev = {"type": "tool_result", "name": step["name"], "result": result}
            else:  # text
                tkey = "demo_validate_done" if key == "validate" else "demo_general_done"
                ev = {"type": "text",
                      "text": _t(req.lang, tkey).format(path=config_path)}

            markdown = _render_event(ev, start_time)
            if markdown is not None:
                yield _sse({"type": "event", "kind": ev["type"],
                            "markdown": markdown})

    return StreamingResponse(stream(), media_type="text/event-stream")
