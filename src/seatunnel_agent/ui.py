"""Gradio Web UI for SeaTunnel Agent.

Run with:  python -m seatunnel_agent.ui
Or:        seatunnel-agent ui
"""

from __future__ import annotations

import json
import re
import tempfile
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import gradio as gr

from .config import Settings, env_float, load_settings
from .agent import SeaTunnelAgent

_DOCS_URL = "https://github.com/ClaireLytt/seatunnel_agent#readme"
_EVENT_POLL_INTERVAL = env_float("UI_EVENT_POLL_INTERVAL", 0.3)
_DEMO_STEP_DELAY = env_float("UI_DEMO_STEP_DELAY", 0.35)
from .history import (
    Session, delete_session, extract_title, list_sessions,
    load_session, new_session_id, rename_session, save_session,
)
from .tools import execute_tool


def _extract_text_part(part: Any) -> str:
    """Extract plain text from a TextMessage, dict, or string."""
    if isinstance(part, dict):
        raw = part.get("text", part)
    else:
        raw = getattr(part, "text", None)
        if raw is None:
            raw = part
    return _unwrap_textmsg_str(str(raw))


def _unwrap_textmsg_str(s: str) -> str:
    """Recursively strip ``{'text': '...', 'type': 'text'}`` wrappers."""
    import ast
    stripped = s.strip()
    if stripped.startswith("{") and "'text':" in stripped and "'type':" in stripped:
        try:
            parsed = ast.literal_eval(stripped)
            if isinstance(parsed, dict) and "text" in parsed:
                return _unwrap_textmsg_str(str(parsed["text"]))
        except (ValueError, SyntaxError):
            pass
    return s


def _normalize_chat(chat_history: list) -> list[dict[str, str]]:
    """Convert Gradio ChatMessage objects to plain dicts."""
    out: list[dict[str, str]] = []
    for msg in chat_history:
        if isinstance(msg, dict):
            role = msg.get("role", "")
            content = msg.get("content", "")
        else:
            role = getattr(msg, "role", "")
            content = getattr(msg, "content", "")
        if isinstance(content, list):
            content = "".join(_extract_text_part(part) for part in content)
        else:
            content = _unwrap_textmsg_str(str(content))
        out.append({"role": str(role), "content": content})
    return out


# ------------------------------------------------------------------
# i18n
# ------------------------------------------------------------------

_I18N: dict[str, dict[str, str]] = {
    "en": {
        "title": "SeaTunnel Pipeline Builder",
        "subtitle": "AI Agent · ReAct Pattern · Auto-diagnose & Fix",
        "mode": "MODE",
        "mode_nl": "Natural Language",
        "mode_run": "Run Config",
        "mode_validate": "Validate Config",
        "mode_diagnose": "Diagnose Log",
        "config_path": "CONFIG / LOG PATH",
        "config_placeholder": "examples/fake_to_console.conf",
        "connect": "Connect",
        "status": "STATUS",
        "status_default": "Not connected",
        "input_placeholder": "Message SeaTunnel Agent...",
        "submit": "Send",
        "demo": "Demo",
        "clear": "Clear",
        "quick_start": "QUICK START",
        "ex1": "Generate 10 fake rows to console",
        "ex2": "Sync MySQL users table to Console",
        "ex3": "Validate examples/fake_to_console.conf",
        "ex1_fill": "Generate 10 fake rows with id, name, age and print to console",
        "ex2_fill": "Create a config to sync MySQL users table to Console",
        "ex3_fill": "Validate examples/fake_to_console.conf",
        "chat_placeholder": "Click **Demo** to see the agent in action, or **Connect** then type a task.",
        "no_settings": "Settings not loaded. Click **Connect** first and make sure `.env` is configured.",
        "demo_default_msg": "Generate a FakeSource to Console config",
        "demo_validate_done": "**Validation complete!** Config file `{path}` has correct syntax with required source and sink sections.",
        "demo_general_done": (
            "**Config generated and validated!**\n\n"
            "Saved to `{path}`:\n"
            "- **Source**: FakeSource (5 fake rows, fields: id/name/age)\n"
            "- **Sink**: Console (print to stdout)\n\n"
            "Ready to run if SeaTunnel is installed."
        ),
        "new_chat": "+ New Chat",
        "history": "History",
        "delete_session": "Delete",
        "no_history": "No conversations yet",
        "settings_label": "SETTINGS",
        "placeholder_title": "How can I help you build a pipeline?",
        "placeholder_hint1": "Generate 10 fake rows to console",
        "placeholder_hint2": "Sync MySQL users table to Console",
        "placeholder_hint3": "Validate examples/fake_to_console.conf",
        "export": "Export",
        "export_empty": "No conversation to export",
        "templates": "TEMPLATES",
        "tpl_none": "-- Select a template --",
        "stop": "Stop",
        "stopped": "Agent stopped by user.",
        "rename": "Rename",
        "delete": "Delete",
        "rename_placeholder": "New name...",
    },
    "zh": {
        "title": "SeaTunnel 数据管道构建器",
        "subtitle": "AI 智能代理 · ReAct 推理模式 · 自动诊断修复",
        "mode": "运行模式",
        "mode_nl": "自然语言描述",
        "mode_run": "运行配置文件",
        "mode_validate": "验证配置",
        "mode_diagnose": "诊断日志",
        "config_path": "配置 / 日志路径",
        "config_placeholder": "examples/fake_to_console.conf",
        "connect": "连接",
        "status": "状态",
        "status_default": "未连接",
        "input_placeholder": "输入你的数据管道任务...",
        "submit": "发送",
        "demo": "演示",
        "clear": "清空",
        "quick_start": "快速开始",
        "ex1": "生成 10 条假数据输出到控制台",
        "ex2": "同步 MySQL 用户表到 Console",
        "ex3": "验证 examples/fake_to_console.conf",
        "ex1_fill": "生成 10 条假数据，字段为 id, name, age，输出到 Console",
        "ex2_fill": "创建一个配置，将 MySQL users 表同步到 Console",
        "ex3_fill": "验证 examples/fake_to_console.conf 配置文件",
        "chat_placeholder": "点击 **演示** 查看 Agent 工作流程，或点 **连接** 后输入任务。",
        "no_settings": "未加载配置。请先点击 **连接**，确保 `.env` 已配置。",
        "demo_default_msg": "帮我生成一个 FakeSource 到 Console 的配置",
        "demo_validate_done": "**验证完成！** 配置文件 `{path}` 语法正确，包含必要的 source 和 sink 部分。",
        "demo_general_done": (
            "**配置已生成并验证通过！**\n\n"
            "配置文件保存在 `{path}`，包含：\n"
            "- **Source**: FakeSource（生成 5 行假数据，字段 id/name/age）\n"
            "- **Sink**: Console（输出到控制台）\n\n"
            "如果安装了 SeaTunnel，可以直接运行此配置。"
        ),
        "new_chat": "+ 新建对话",
        "history": "历史记录",
        "delete_session": "删除",
        "no_history": "暂无历史记录",
        "settings_label": "设置",
        "placeholder_title": "我能帮你构建什么管道？",
        "placeholder_hint1": "生成 10 条假数据到控制台",
        "placeholder_hint2": "同步 MySQL 用户表到 Console",
        "placeholder_hint3": "验证 examples/fake_to_console.conf",
        "export": "导出",
        "export_empty": "没有可导出的对话",
        "templates": "配置模板",
        "tpl_none": "-- 选择模板 --",
        "stop": "停止",
        "stopped": "已被用户中断。",
        "rename": "重命名",
        "delete": "删除",
        "rename_placeholder": "新名称...",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N.get(lang, _I18N["en"]).get(key, _I18N["en"].get(key, key))


def _build_template_choices(lang: str) -> list[tuple[str, str]]:
    from .templates import TEMPLATES
    none_label = _t(lang, "tpl_none")
    choices: list[tuple[str, str]] = [(none_label, "")]
    for t in TEMPLATES:
        params = ", ".join(p["name"] for p in t.parameters[:3])
        if len(t.parameters) > 3:
            params += ", ..."
        label = f"{t.name}  ({t.description})"
        choices.append((label, t.name))
    return choices


def _template_to_prompt(template_name: str, lang: str) -> str:
    if not template_name:
        return ""
    from .templates import get_template
    tpl = get_template(template_name)
    if tpl is None:
        return ""
    params_hint = ", ".join(
        f"{p['name']}={p['default']}" for p in tpl.parameters if p.get("default")
    )
    if lang == "zh":
        return f"使用 {tpl.name} 模板创建管道配置（{params_hint}）"
    return f"Create a pipeline config using the {tpl.name} template ({params_hint})"


# ------------------------------------------------------------------
# Demo mode
# ------------------------------------------------------------------

_DEMO_STEPS: dict[str, list[dict[str, Any]]] = {
    "validate": [
        {"type": "thinking", "text": "I need to read the config file first, then validate its structure."},
        {"type": "tool_call", "name": "read_config"},
        {"type": "tool_result", "name": "read_config"},
        {"type": "thinking", "text": "Config loaded. Now checking syntax and required sections with validate_config."},
        {"type": "tool_call", "name": "validate_config"},
        {"type": "tool_result", "name": "validate_config"},
        {"type": "text"},
        {"type": "final_answer"},
    ],
    "general": [
        {"type": "thinking", "text": "Let me check available connectors first."},
        {"type": "tool_call", "name": "list_connectors"},
        {"type": "tool_result", "name": "list_connectors"},
        {"type": "thinking", "text": "Now I'll generate a FakeSource → Console config and validate it."},
        {"type": "tool_call", "name": "write_config"},
        {"type": "tool_result", "name": "write_config"},
        {"type": "tool_call", "name": "validate_config"},
        {"type": "tool_result", "name": "validate_config"},
        {"type": "text"},
        {"type": "final_answer"},
    ],
}

_DEMO_CONFIG = """\
env {
  parallelism = 1
  job.mode = "BATCH"
}

source {
  FakeSource {
    schema = {
      fields {
        id = "int"
        name = "string"
        age = "int"
      }
    }
    rows = 5
  }
}

transform {
}

sink {
  Console {}
}
"""


def _run_demo(
    user_message: str,
    chat_history: list[dict[str, str]],
    config_path: str,
    lang: str,
) -> list[dict[str, str]]:
    import tempfile, os

    fake_settings = Settings(
        api_key="demo", seatunnel_home=".", seatunnel_bin="", max_retries=3,
    )

    has_config = config_path.strip() and os.path.isfile(config_path.strip())
    key = "validate" if has_config else "general"
    steps = _DEMO_STEPS[key]

    if not has_config:
        demo_path = os.path.join(tempfile.gettempdir(), "demo_fake_to_console.conf")
        with open(demo_path, "w", encoding="utf-8") as f:
            f.write(_DEMO_CONFIG)
        config_path = demo_path
    else:
        config_path = config_path.strip()

    collector = EventCollector()

    for step in steps:
        t = step["type"]
        time.sleep(_DEMO_STEP_DELAY)

        if t == "thinking":
            collector.on_event("thinking", {"text": step["text"]})
        elif t == "tool_call":
            name = step["name"]
            inp = ({"config_path": config_path, "content": _DEMO_CONFIG}
                   if name == "write_config"
                   else {"config_path": config_path}
                   if name in ("read_config", "validate_config")
                   else {})
            collector.on_event("tool_call", {"name": name, "input": inp})
        elif t == "tool_result":
            name = step["name"]
            inp = ({"config_path": config_path, "content": _DEMO_CONFIG}
                   if name == "write_config"
                   else {"config_path": config_path}
                   if name in ("read_config", "validate_config")
                   else {})
            result = execute_tool(name, inp, fake_settings)
            collector.on_event("tool_result", {"name": name, "result": result})
        elif t == "text":
            tkey = "demo_validate_done" if key == "validate" else "demo_general_done"
            text = _t(lang, tkey).format(path=config_path)
            collector.on_event("text", {"text": text})
        elif t == "final_answer":
            collector.on_event("final_answer", {"text": "done"})

    return _format_events_as_chat(collector.snapshot())


# ------------------------------------------------------------------
# Event collector
# ------------------------------------------------------------------

class EventCollector:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.lock = threading.Lock()
        self.done = False
        self._new_event = threading.Event()

    def on_event(self, event_type: str, data: dict[str, Any]) -> None:
        with self.lock:
            self.events.append({"type": event_type, **data})
            if event_type == "final_answer":
                self.done = True
        self._new_event.set()

    def wait_for_event(self, timeout: float = 0.3) -> None:
        self._new_event.wait(timeout)
        self._new_event.clear()

    @property
    def event_count(self) -> int:
        with self.lock:
            return len(self.events)

    def snapshot(self) -> list[dict[str, Any]]:
        with self.lock:
            return list(self.events)

    def snapshot_since(self, start: int) -> list[dict[str, Any]]:
        with self.lock:
            return self.events[start:]


# ------------------------------------------------------------------
# Format events -> chat messages
# ------------------------------------------------------------------

_TOOL_EMOJI = {
    "run_seatunnel_job": "\U0001f680",
    "write_config": "✏️",
    "read_config": "\U0001f4d6",
    "read_log": "\U0001f4cb",
    "validate_config": "✅",
    "list_connectors": "\U0001f50c",
    "test_connection": "\U0001f50c",
    "list_templates": "\U0001f4cb",
    "use_template": "\U0001f4dd",
    "query_connector_docs": "\U0001f4d6",
    "list_config_versions": "\U0001f4dc",
    "run_batch": "\U0001f4e6",
    "restore_config_version": "\U0001f504",
    "delete_config": "\U0001f5d1",
    "compare_config_versions": "\U0001f500",
    "explain_config": "\U0001f4cb",
}


def _format_events_as_chat(events: list[dict[str, Any]], start_time: float | None = None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    delta_buffer: list[str] = []

    def _flush_delta() -> None:
        if delta_buffer:
            accumulated = "".join(delta_buffer)
            if accumulated.strip():
                messages.append({"role": "assistant", "content": accumulated + " ▌"})
            delta_buffer.clear()

    for ev in events:
        t = ev["type"]

        if t == "text_delta":
            delta_buffer.append(ev.get("text", ""))
            continue
        if t == "usage":
            inp = ev.get("input_tokens", 0)
            out = ev.get("output_tokens", 0)
            if inp or out:
                messages.append({"role": "assistant",
                                 "content": f"📊 Tokens: {inp:,} in / {out:,} out"})
            continue
        if t == "text":
            delta_buffer.clear()
        elif delta_buffer:
            _flush_delta()

        if t == "step":
            iteration = ev.get("iteration", "?")
            phase = ev.get("phase", "")
            label = {"thinking": "Thinking...", "executing_tools": "Executing tools..."}.get(phase, phase)
            elapsed_str = ""
            if start_time is not None:
                elapsed_str = f" ({time.time() - start_time:.1f}s)"
            messages.append({"role": "assistant",
                             "content": f"⏳ **Step {iteration}** — {label}{elapsed_str}"})
        elif t == "thinking":
            text = ev.get("text", "")
            if text:
                preview = text[:600] + ("..." if len(text) > 600 else "")
                messages.append({"role": "assistant", "content": f"\U0001f4ad **Thinking**\n\n{preview}"})
        elif t == "text":
            text = ev.get("text", "")
            if text:
                messages.append({"role": "assistant", "content": text})
        elif t == "tool_call":
            name = ev.get("name", "?")
            inp = ev.get("input", {})
            emoji = _TOOL_EMOJI.get(name, "\U0001f527")
            args_lines = "\n".join(f"  {k}: {repr(v)[:120]}" for k, v in inp.items() if k != "content")
            if "content" in inp:
                args_lines += f"\n  content: ({len(inp['content'])} chars)"
            messages.append({"role": "assistant",
                             "content": f"{emoji} **Tool Call: `{name}`**\n```\n{args_lines}\n```"})
        elif t == "tool_result":
            name = ev.get("name", "?")
            raw = ev.get("result", "{}")
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                data = {"raw": raw[:500]}

            if data.get("error"):
                badge, summary = "❌", f"Error: {data['error'][:300]}"
            elif data.get("reachable") is True:
                badge, summary = "✅", data.get("message", "Reachable")
            elif data.get("reachable") is False:
                badge, summary = "❌", data.get("message", "Unreachable")
            elif "stdout" in data:
                badge = "✅" if data.get("success") else "❌"
                parts = []
                if data.get("metrics"):
                    m = data["metrics"]
                    metric_lines = []
                    if "total_read_count" in m:
                        metric_lines.append(f"Read: **{m['total_read_count']:,}** rows")
                    if "total_write_count" in m:
                        metric_lines.append(f"Written: **{m['total_write_count']:,}** rows")
                    if "total_read_bytes" in m:
                        metric_lines.append(f"Read: **{m['total_read_bytes']:,}** bytes")
                    if "duration_ms" in m:
                        secs = m["duration_ms"] / 1000
                        metric_lines.append(f"Duration: **{secs:.1f}s**")
                    if metric_lines:
                        parts.append("**Metrics:**\n" + "\n".join(metric_lines))
                if data.get("stdout"):
                    parts.append(f"stdout:\n```\n{data['stdout'][:400]}\n```")
                if data.get("stderr"):
                    parts.append(f"stderr:\n```\n{data['stderr'][:300]}\n```")
                summary = "\n".join(parts) or "(no output)"
            elif data.get("success") is True:
                badge, summary = "✅", "Success"
                if data.get("version"):
                    summary += f" (version {data['version']})"
                if data.get("diff"):
                    summary += f"\n\n**Changes:**\n```diff\n{data['diff'][:800]}\n```"
                elif data.get("had_changes") is False:
                    summary += " (no changes)"
            elif data.get("valid") is True:
                badge, summary = "✅", "Config is valid"
                if data.get("warnings"):
                    summary += "\n⚠️ " + "; ".join(data["warnings"])
            elif data.get("valid") is False:
                badge = "❌"
                summary = "Invalid config\n" + "\n".join(f"  - {e}" for e in data.get("errors", []))
            elif "content" in data:
                c = data["content"]
                badge, summary = "\U0001f4c4", f"```\n{c[:400]}{'...' if len(c)>400 else ''}\n```"
            elif "templates" in data:
                tpls = data["templates"]
                lines = [f"  - **{t['name']}**: {t['description']}" for t in tpls[:10]]
                badge, summary = "\U0001f4cb", f"Found {data.get('count', len(tpls))} templates:\n" + "\n".join(lines)
            elif "required_params" in data or "param_detail" in data:
                badge = "\U0001f4d6"
                if "param_detail" in data:
                    p = data["param_detail"]
                    summary = f"**{p['name']}** ({p['type']})\n{p['description']}\nExample: `{p['example']}`"
                else:
                    req = data.get("required_params", [])
                    opt = data.get("optional_params", [])
                    lines_r = [f"**{data.get('connector_name', '')}** — {data.get('description', '')}"]
                    if req:
                        lines_r.append(f"\nRequired ({len(req)}):")
                        for p in req[:10]:
                            lines_r.append(f"  - `{p['name']}` ({p['type']}): {p['description']}")
                    if opt:
                        lines_r.append(f"\nOptional ({len(opt)}):")
                        for p in opt[:5]:
                            lines_r.append(f"  - `{p['name']}` ({p['type']}): {p['description']}")
                    summary = "\n".join(lines_r)
            elif "versions" in data and isinstance(data["versions"], list):
                badge = "\U0001f4dc"
                vers = data["versions"]
                if not vers:
                    summary = "No version history found for this config."
                else:
                    lines_v = [f"**{data.get('config_path', 'Config')}** — {len(vers)} version(s):"]
                    for v in vers[-10:]:
                        size_kb = v.get("size_bytes", 0) / 1024
                        lines_v.append(f"  - v{v['version']} — {v['timestamp']} ({size_kb:.1f} KB)")
                    summary = "\n".join(lines_v)
            elif "results" in data and "passed" in data and "failed" in data:
                badge = "✅" if data["failed"] == 0 else "❌"
                header = f"**Batch Run**: {data['passed']}/{data['total']} passed"
                if data.get("stopped_early"):
                    header += " (stopped early)"
                batch_lines = [header, ""]
                for r in data.get("results", []):
                    status_icon = "✅" if r.get("success") else "❌"
                    line = f"{status_icon} `{r['config_path']}`"
                    if r.get("error"):
                        line += f" — {r['error'][:100]}"
                    batch_lines.append(line)
                summary = "\n".join(batch_lines)
            else:
                badge = "\U0001f4e6"
                summary = f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)[:500]}\n```"
            messages.append({"role": "assistant", "content": f"{badge} **Result: `{name}`**\n\n{summary}"})

    if delta_buffer:
        _flush_delta()

    return messages


# ------------------------------------------------------------------
# Streaming runner
# ------------------------------------------------------------------

def _run_agent_streaming(user_message, chat_history, mode, config_path, settings, agent_holder,
                         collector_holder=None):
    chat_history = _normalize_chat(chat_history)
    collector = EventCollector()
    if collector_holder is not None:
        collector_holder["current"] = collector
    is_first = agent_holder.get("agent") is None
    if is_first:
        agent = SeaTunnelAgent(settings, on_event=collector.on_event)
        agent_holder["agent"] = agent
    else:
        agent = agent_holder["agent"]
        agent._on_event = collector.on_event

    error_msg = None
    start_time = time.time()

    def _worker():
        nonlocal error_msg
        try:
            if is_first:
                if mode == "run_config" and config_path.strip():
                    agent.run_with_config(config_path.strip())
                elif mode == "validate" and config_path.strip():
                    agent.validate_only(config_path.strip())
                elif mode == "diagnose" and config_path.strip():
                    agent.diagnose_log(config_path.strip())
                else:
                    agent.run(user_message)
            else:
                agent.chat(user_message)
        except Exception as e:
            error_msg = str(e)
            collector.on_event("final_answer", {"text": f"Error: {e}"})

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    prev_count = 0
    while not collector.done:
        collector.wait_for_event(timeout=_EVENT_POLL_INTERVAL)
        events = collector.snapshot()
        if len(events) > prev_count:
            prev_count = len(events)
            yield chat_history + [{"role": "user", "content": user_message}] + _format_events_as_chat(events, start_time)
    thread.join(timeout=5)
    if thread.is_alive():
        import logging
        logging.getLogger(__name__).warning(
            "Agent worker thread is still running after stop/finish; "
            "it will exit at the next loop-iteration check."
        )
    elapsed = time.time() - start_time
    final = _format_events_as_chat(collector.snapshot(), start_time)
    if error_msg:
        final.append({"role": "assistant", "content": f"⚠️ **Error**: {error_msg}"})
    final.append({"role": "assistant", "content": f"⏱️ Completed in {elapsed:.1f}s"})
    yield chat_history + [{"role": "user", "content": user_message}] + final


# ------------------------------------------------------------------
# History helpers
# ------------------------------------------------------------------

def _build_history_choices() -> list[tuple[str, str]]:
    sessions = list_sessions()
    choices = []
    for s in sessions:
        ts = s.get("updated_at", "")[:16].replace("T", " ")
        title = s.get("title", "Untitled")
        n = s.get("msg_count", 0)
        count_tag = f" ({n} msgs)" if n else ""
        label = f"{ts}  {title}{count_tag}" if ts else f"{title}{count_tag}"
        choices.append((label, s["id"]))
    return choices


def _save_current_session(
    session_id: str,
    chat_history: list[dict[str, str]],
    agent_holder: dict[str, Any],
) -> str:
    chat_history = _normalize_chat(chat_history)
    if not chat_history:
        return session_id
    if not session_id:
        session_id = new_session_id()
    agent = agent_holder.get("agent")
    agent_msgs = agent.messages if agent else []
    from .history import now_iso
    title = extract_title(chat_history)
    agent_ctx = agent.context if agent else {}
    existing = load_session(session_id)
    created = existing.created_at if existing else now_iso()
    session = Session(
        session_id=session_id,
        title=title,
        created_at=created,
        updated_at=now_iso(),
        chat_messages=chat_history,
        agent_messages=agent_msgs,
        agent_context=agent_ctx,
    )
    save_session(session)
    return session_id


# ------------------------------------------------------------------
# Dynamic HTML builders
# ------------------------------------------------------------------

def _build_placeholder(lang: str) -> str:
    docs_text = "\U0001f4d6 Docs — 查看使用文档" if lang == "zh" else "\U0001f4d6 Docs — View documentation"
    return f'''<div class="st-empty-state">
  <div class="st-empty-logo">ST</div>
  <div class="st-empty-title">{_t(lang, "placeholder_title")}</div>
  <div class="st-empty-hints">
    <div class="st-hint-card">{_t(lang, "placeholder_hint1")}</div>
    <div class="st-hint-card">{_t(lang, "placeholder_hint2")}</div>
    <div class="st-hint-card">{_t(lang, "placeholder_hint3")}</div>
  </div>
  <a href="{_DOCS_URL}"
     target="_blank" class="st-docs-link">{docs_text}</a>
</div>'''


def _export_session(
    chat_history: list[dict[str, str]],
    session_id: str,
    created_configs: list[str] | None = None,
    settings: Settings | None = None,
) -> str | None:
    chat_history = _normalize_chat(chat_history)
    if not chat_history:
        return None

    title = extract_title(chat_history)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md_lines = [
        "# SeaTunnel Agent Session Report",
        "",
        f"- **Title**: {title}",
        f"- **Session ID**: {session_id}",
        f"- **Exported at**: {timestamp}",
    ]
    if settings:
        md_lines.append(f"- **Model**: {settings.model_name}")
        md_lines.append(f"- **Provider**: {settings.llm_provider}")
    md_lines += [
        "",
        "---",
        "",
    ]

    for msg in chat_history:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        header = "## User" if role == "user" else "## Assistant"
        md_lines.append(f"{header}\n\n{content}\n")

    config_files: list[Path] = []
    for p in (created_configs or []):
        fp = Path(p)
        if fp.is_file():
            config_files.append(fp)

    if config_files:
        md_lines.append("\n---\n\n## Generated Config Files\n")
        for fp in config_files:
            md_lines.append(f"- `{fp.name}`")

    report_md = "\n".join(md_lines)

    export_dir = Path(tempfile.gettempdir()) / "seatunnel_exports"
    export_dir.mkdir(exist_ok=True)
    zip_name = f"seatunnel_session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = export_dir / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("report.md", report_md)
        for fp in config_files:
            zf.write(fp, f"configs/{fp.name}")

    return str(zip_path)


# ------------------------------------------------------------------
# Build UI
# ------------------------------------------------------------------

_MODE_MAP = {
    "Natural Language": "run", "Run Config": "run_config",
    "Validate Config": "validate", "Diagnose Log": "diagnose",
    "自然语言描述": "run", "运行配置文件": "run_config",
    "验证配置": "validate", "诊断日志": "diagnose",
}


def _build_hub_html() -> str:
    return '''<div class="st-hub" id="st-hub">
  <div class="st-hub-lang-row">
    <select id="st-hub-lang" onchange="var l=this.value;document.querySelectorAll('#st-hub [data-'+l+']').forEach(function(e){e.textContent=e.getAttribute('data-'+l)});">
      <option value="en" selected>English</option>
      <option value="zh">中文</option>
    </select>
  </div>
  <div class="st-hub-header">
    <div class="st-hub-title" data-en="SeaTunnel Agent Platform" data-zh="SeaTunnel Agent 工作台">SeaTunnel Agent Platform</div>
    <div class="st-hub-subtitle" data-en="AI Agent Workspace · Choose an agent to start" data-zh="AI Agent 工作台 · 选择一个能力开始">AI Agent Workspace · Choose an agent to start</div>
  </div>
  <div class="st-hub-grid">
    <a class="st-hub-card" href="/seatunnel">
      <div class="st-hub-logo" style="background:#f76707;">ST</div>
      <div class="st-hub-card-title" data-en="SeaTunnel Pipeline Builder" data-zh="SeaTunnel Pipeline Builder · 数据管道构建">SeaTunnel Pipeline Builder</div>
      <div class="st-hub-card-desc" data-en="Generate / validate / run SeaTunnel configs with natural language, auto-diagnose &amp; fix" data-zh="自然语言生成 / 验证 / 运行 SeaTunnel 配置，自动诊断修复">Generate / validate / run SeaTunnel configs with natural language, auto-diagnose &amp; fix</div>
      <div class="st-hub-enter" style="color:#f76707;" data-en="Enter →" data-zh="进入 →">Enter →</div>
    </a>
    <a class="st-hub-card" href="/text2sql">
      <div class="st-hub-logo" style="background:#0ea5e9;">SQL</div>
      <div class="st-hub-card-title" data-en="Text2SQL · Chat BI" data-zh="Text2SQL · Chat BI · 智能问数">Text2SQL · Chat BI</div>
      <div class="st-hub-card-desc" data-en="Ask in natural language → auto match table schema → generate &amp; run Hive SQL → preview &amp; CSV export" data-zh="自然语言提问 → 自动匹配表结构 → 生成并执行 Hive SQL → 结果预览与 CSV 导出">Ask in natural language → auto match table schema → generate &amp; run Hive SQL → preview &amp; CSV export</div>
      <div class="st-hub-enter" style="color:#0ea5e9;" data-en="Enter →" data-zh="进入 →">Enter →</div>
    </a>
    <a class="st-hub-card" href="/datacompare">
      <div class="st-hub-logo" style="background:#8b5cf6;">⇄</div>
      <div class="st-hub-card-title" data-en="Data Comparison" data-zh="数据比对">Data Comparison</div>
      <div class="st-hub-card-desc" data-en="Compare schemas, row counts, and data across two data sources" data-zh="跨数据源比对表结构、行数、数据差异">Compare schemas, row counts, and data across two data sources</div>
      <div class="st-hub-enter" style="color:#8b5cf6;" data-en="Enter →" data-zh="进入 →">Enter →</div>
    </a>
    <a class="st-hub-card" href="/sqlreview">
      <div class="st-hub-logo" style="background:#10b981;">CR</div>
      <div class="st-hub-card-title" data-en="SQL Code Review" data-zh="SQL 代码审查">SQL Code Review</div>
      <div class="st-hub-card-desc" data-en="Static + LLM review for Hive / Spark / Flink / MaxCompute SQL — performance, quality &amp; standards" data-zh="Hive / Spark / Flink / MaxCompute SQL 静态 + LLM 审查 — 性能、质量与规范">Static + LLM review for Hive / Spark / Flink / MaxCompute SQL — performance, quality &amp; standards</div>
      <div class="st-hub-enter" style="color:#10b981;" data-en="Enter →" data-zh="进入 →">Enter →</div>
    </a>
    <a class="st-hub-card" href="/uitest">
      <div class="st-hub-logo" style="background:#f59e0b;">UT</div>
      <div class="st-hub-card-title" data-en="UI Testing Agent" data-zh="UI 测试 Agent">UI Testing Agent</div>
      <div class="st-hub-card-desc" data-en="Browser-driven regression for the Gradio pages — YAML cases, LLM fuzzy assertions, HTML reports" data-zh="真实浏览器驱动的页面自动回归 — YAML 用例、LLM 模糊断言、HTML 报告">Browser-driven regression for the Gradio pages — YAML cases, LLM fuzzy assertions, HTML reports</div>
      <div class="st-hub-enter" style="color:#f59e0b;" data-en="Enter →" data-zh="进入 →">Enter →</div>
    </a>
    <div class="st-hub-card st-hub-card-soon">
      <div class="st-hub-logo" style="background:#e5e7eb;color:#9ca3af;">+</div>
      <div class="st-hub-card-title" style="color:#9ca3af;" data-en="More Agents" data-zh="更多 Agent">More Agents</div>
      <div class="st-hub-card-desc" data-en="More agent capabilities coming soon..." data-zh="更多 Agent 能力筹备中...">More agent capabilities coming soon...</div>
    </div>
  </div>
</div>'''


# Drag-to-resize for the left sidebar: restores the saved width, appends a
# handle to .st-page-row (not inside .st-sidebar — sidebar_fix.js forces
# inline width on its direct div children) and drives --st-sidebar-w.
_SIDEBAR_RESIZE_JS = """
() => {
    if (window.__stSidebarResize) return;
    window.__stSidebarResize = true;
    const MIN = 180, MAX = 520, KEY = 'stSidebarW';
    try {
        const saved = parseInt(localStorage.getItem(KEY), 10);
        if (saved >= MIN && saved <= MAX) {
            document.documentElement.style.setProperty('--st-sidebar-w', saved + 'px');
        }
    } catch (e) {}
    let tries = 0;
    const init = () => {
        const row = document.querySelector('.st-page-row');
        const sb = row && row.querySelector('.st-sidebar');
        if (!row || !sb) {
            if (tries++ < 50) setTimeout(init, 200);
            return;
        }
        // The Data Comparison sidebar has its own CSS resize (720px wide);
        // the fixed-position handle would float mid-sidebar and swallow
        // clicks on anything underneath it.
        if (sb.classList.contains('st-dc-sidebar')) return;
        if (row.querySelector('.st-sidebar-resize')) return;
        const handle = document.createElement('span');
        handle.className = 'st-sidebar-resize';
        handle.title = 'Drag to resize sidebar';
        row.appendChild(handle);
        const syncVisible = () => {
            handle.style.display =
                getComputedStyle(sb).display === 'none' ? 'none' : '';
        };
        syncVisible();
        new MutationObserver(syncVisible)
            .observe(sb, {attributes: true, attributeFilter: ['style', 'class']});
        let startX = 0, startW = 0;
        const onMove = (e) => {
            const w = Math.min(MAX, Math.max(MIN, startW + e.clientX - startX));
            document.documentElement.style.setProperty('--st-sidebar-w', w + 'px');
        };
        const onUp = () => {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            handle.classList.remove('st-resizing');
            document.body.classList.remove('st-sidebar-dragging');
            try {
                const w = parseInt(
                    getComputedStyle(document.documentElement)
                        .getPropertyValue('--st-sidebar-w'), 10);
                if (w) localStorage.setItem(KEY, String(w));
            } catch (e) {}
        };
        handle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            startX = e.clientX;
            startW = sb.getBoundingClientRect().width;
            handle.classList.add('st-resizing');
            document.body.classList.add('st-sidebar-dragging');
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    };
    init();
}
"""


def create_ui() -> gr.Blocks:
    """Multipage app: hub landing page + one dedicated page per agent."""
    from .text2sql_ui import render_text2sql_page, render_history_page, render_favorites_page, render_schema_browser_page
    from .data_comparison_ui import render_data_comparison_page
    from .sql_review_ui import render_sql_review_page

    _hide_sub_nav_js = """
    () => {
        function hide() {
            document.querySelectorAll('nav a, .navigation a, a[href*="history"], a[href*="favorites"]').forEach(a => {
                const t = a.textContent.trim();
                const h = a.getAttribute('href') || '';
                if (t === 'Query History' || t === 'SQL Favorites'
                    || h.includes('/history') || h.includes('/favorites')) {
                    a.style.display = 'none';
                }
            });
        }
        hide();
        new MutationObserver(hide).observe(document.body, {childList: true, subtree: true});

        if (!document._tabFillReady) {
            document._tabFillReady = true;
            document.addEventListener('keydown', function(e) {
                if (e.key !== 'Tab') return;
                var el = e.target;
                if (el.tagName !== 'INPUT' && el.tagName !== 'TEXTAREA') return;
                if (el.value.trim() !== '' || !el.placeholder) return;
                e.preventDefault();
                var proto = el.tagName === 'TEXTAREA'
                    ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                setter.call(el, el.placeholder);
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
            });
        }
    }
    """

    with gr.Blocks(
        title="SeaTunnel Agent",
        fill_height=True,
        fill_width=True,
    ) as app:
        gr.HTML(_build_hub_html())
        app.load(fn=None, js=_hide_sub_nav_js)

    with app.route("SeaTunnel", "/seatunnel"):
        _render_seatunnel_page(app)
        app.load(fn=None, js=_SIDEBAR_RESIZE_JS)

    with app.route("Text2SQL", "/text2sql"):
        render_text2sql_page(app)
        app.load(fn=None, js=_SIDEBAR_RESIZE_JS)

    with app.route("Query History", "/history"):
        render_history_page(app)

    with app.route("SQL Favorites", "/favorites"):
        render_favorites_page(app)

    with app.route("Schema Browser", "/schema-browser"):
        render_schema_browser_page(app)

    with app.route("Data Comparison", "/datacompare"):
        render_data_comparison_page(app)
        app.load(fn=None, js=_SIDEBAR_RESIZE_JS)

    with app.route("SQL Review", "/sqlreview"):
        render_sql_review_page(app)

    with app.route("UI Testing", "/uitest"):
        from .ui_testing.gradio_page import render_uitest_page
        render_uitest_page(app)

    return app


def _render_seatunnel_page(app: gr.Blocks) -> None:
    settings_holder: dict[str, Settings | None] = {"current": None}
    agent_holder: dict[str, SeaTunnelAgent | None] = {"agent": None}
    collector_holder: dict[str, EventCollector | None] = {"current": None}

    lang = "en"

    # ── Callbacks ──

    def _load_settings_safe(lang):
        try:
            settings_holder["current"] = load_settings()
            s = settings_holder["current"]

            def _warmup_llm():
                """Pre-import LLM SDK so the first chat doesn't pay the cost."""
                try:
                    if s.llm_provider == "anthropic":
                        import anthropic  # noqa: F401
                    else:
                        import openai  # noqa: F401
                except Exception:
                    pass

            import threading
            threading.Thread(target=_warmup_llm, daemon=True).start()

            if lang == "zh":
                return f"✅ 连接成功，模型: {s.model_name}"
            return f"✅ Connected, Model: {s.model_name}"
        except Exception as e:
            settings_holder["current"] = None
            if lang == "zh":
                return f"❌ 连接失败: {e}"
            return f"❌ Failed: {e}"

    def _handle_submit(msg, history, mode_text, cfg, lang, sid):
        no_save = gr.update()
        if not msg.strip() and not cfg.strip():
            yield history, sid, no_save
            return
        if not sid:
            sid = new_session_id()
        settings = settings_holder.get("current")
        if settings is None:
            yield history + [
                {"role": "user", "content": msg},
                {"role": "assistant", "content": _t(lang, "no_settings")},
            ], sid, no_save
            return
        mode_key = _MODE_MAP.get(mode_text, "run")
        final_chat = history
        for update in _run_agent_streaming(msg, history, mode_key, cfg, settings, agent_holder, collector_holder):
            final_chat = update
            yield update, sid, no_save
        sid = _save_current_session(sid, final_chat, agent_holder)
        choices = _build_history_choices()
        yield final_chat, sid, gr.update(choices=choices, value=sid)

    def _handle_demo(msg, history, cfg, lang, sid):
        if not msg.strip():
            msg = _t(lang, "demo_default_msg")
        if not sid:
            sid = new_session_id()
        new = _run_demo(msg, history, cfg, lang)
        final = history + [{"role": "user", "content": msg}] + new
        sid = _save_current_session(sid, final, agent_holder)
        choices = _build_history_choices()
        return final, sid, gr.update(choices=choices, value=sid)

    def _new_chat(lang):
        agent_holder["agent"] = None
        sid = new_session_id()
        choices = _build_history_choices()
        return sid, [], gr.update(choices=choices, value=None)

    def _load_history(selected_sid, lang):
        if not selected_sid:
            return [], ""
        session = load_session(selected_sid)
        if not session:
            return [], ""
        if session.agent_messages:
            settings = settings_holder.get("current")
            if settings:
                agent = SeaTunnelAgent(settings, on_event=lambda *_: None)
                agent.messages = list(session.agent_messages)
                if session.agent_context:
                    agent.context = dict(session.agent_context)
                agent_holder["agent"] = agent
        return session.chat_messages, selected_sid

    def _do_delete(sid, lang):
        if sid:
            delete_session(sid)
        agent_holder["agent"] = None
        choices = _build_history_choices()
        return "", [], gr.update(choices=choices, value=None), gr.update(visible=False), gr.update(visible=False)

    def _show_actions(selected_sid):
        has_sel = bool(selected_sid)
        return gr.update(visible=has_sel), gr.update(visible=False)

    def _open_rename(sid):
        if not sid:
            return gr.update(), gr.update(), gr.update()
        session = load_session(sid)
        title = session.title if session else ""
        return gr.update(visible=False), gr.update(visible=True), gr.update(value=title)

    def _confirm_rename(sid, new_title):
        if sid and new_title.strip():
            rename_session(sid, new_title.strip())
        choices = _build_history_choices()
        return gr.update(choices=choices, value=sid), gr.update(visible=True), gr.update(visible=False)

    def _cancel_rename():
        return gr.update(visible=True), gr.update(visible=False)

    def _on_page_load():
        choices = _build_history_choices()
        return gr.update(choices=choices, value=None)

    def _switch_lang(lang):
        modes = [_t(lang, k) for k in ("mode_nl", "mode_run", "mode_validate", "mode_diagnose")]
        return (
            gr.update(choices=modes, value=modes[0], label=_t(lang, "mode")),
            gr.update(label=_t(lang, "config_path"), placeholder=_t(lang, "config_placeholder")),
            gr.update(value=_t(lang, "connect")),
            gr.update(label=_t(lang, "status"), value=_t(lang, "status_default")),
            gr.update(placeholder=_t(lang, "input_placeholder")),
            gr.update(value=_t(lang, "demo")),
            gr.update(value=_t(lang, "new_chat")),
            gr.update(label=_t(lang, "history")),
            gr.update(placeholder=_build_placeholder(lang)),
            gr.update(label=_t(lang, "export")),
            gr.update(choices=_build_template_choices(lang), value="", label=_t(lang, "templates")),
            gr.update(value=f"✏ {_t(lang, 'rename')}"),
            gr.update(value=f"✕ {_t(lang, 'delete')}"),
            gr.update(placeholder=_t(lang, "rename_placeholder")),
        )

    # ── Layout ──

    with gr.Row(elem_classes=["st-page-row"]):
        lang_state = gr.State("en")
        session_state = gr.State("")

        # ── Left panel (sidebar) ──
        with gr.Column(scale=0, min_width=260, elem_classes=["st-sidebar"], elem_id="seatunnel-sidebar") as sidebar_col:
            sidebar_toggle = gr.Button("☰", size="sm", elem_classes=["st-sidebar-toggle"])
            new_chat_btn = gr.Button(
                _t(lang, "new_chat"),
                variant="primary",
                size="sm",
                elem_classes=["st-new-chat-btn"],
            )
            history_dd = gr.Dropdown(
                choices=[],
                value=None,
                label=_t(lang, "history"),
                interactive=True,
                elem_classes=["st-history-dd"],
            )
            with gr.Row(visible=False, elem_classes=["st-action-row"]) as action_row:
                rename_btn = gr.Button(f"✏ {_t(lang, 'rename')}", size="sm", scale=1, elem_classes=["st-action-btn"])
                delete_btn = gr.Button(f"✕ {_t(lang, 'delete')}", variant="stop", size="sm", scale=1, elem_classes=["st-action-btn"])
            with gr.Row(visible=False, elem_classes=["st-rename-row"]) as rename_row:
                rename_input = gr.Textbox(show_label=False, placeholder=_t(lang, "rename_placeholder"), scale=3, lines=1, elem_classes=["st-rename-input"])
                rename_ok = gr.Button("✓", size="sm", scale=0, min_width=36, elem_classes=["st-rename-ok"])
                rename_cancel = gr.Button("✕", size="sm", scale=0, min_width=36, elem_classes=["st-rename-cancel"])

            mode = gr.Dropdown(
                choices=[_t(lang, k) for k in ("mode_nl", "mode_run", "mode_validate", "mode_diagnose")],
                value=_t(lang, "mode_nl"),
                label=_t(lang, "mode"),
                elem_classes=["st-sidebar-control"],
            )
            config_path = gr.Textbox(
                label=_t(lang, "config_path"),
                placeholder=_t(lang, "config_placeholder"),
                elem_classes=["st-sidebar-control"],
            )
            template_dd = gr.Dropdown(
                choices=_build_template_choices(lang),
                value="",
                label=_t(lang, "templates"),
                interactive=True,
                elem_classes=["st-sidebar-control"],
            )
            load_btn = gr.Button(_t(lang, "connect"), variant="secondary", size="sm", elem_classes=["st-connect-btn"])
            status_box = gr.Textbox(label=_t(lang, "status"), interactive=False, value=_t(lang, "status_default"), elem_classes=["st-sidebar-status"])
            export_btn = gr.DownloadButton(_t(lang, "export"), variant="secondary", size="sm", elem_classes=["st-connect-btn"])

        # ── Right panel (chat) ──
        with gr.Column(scale=1, elem_classes=["st-main"]):
            with gr.Row(elem_classes=["st-topbar-row"]):
                sidebar_open_btn = gr.Button("☰", size="sm", visible=False, elem_classes=["st-sidebar-open-btn"])
                gr.HTML('<div class="st-topbar-spacer"></div>')
                home_btn = gr.Button("\U0001f3e0", size="sm", elem_classes=["st-home-btn"])
                lang_dd = gr.Dropdown(
                    choices=["English", "中文"],
                    value="English",
                    show_label=False,
                    container=False,
                    min_width=140,
                    elem_classes=["st-lang-dd"],
                )

            chatbot = gr.Chatbot(
                show_label=False,
                placeholder=_build_placeholder(lang),
                layout="panel",
                buttons=["copy"],
                elem_classes=["st-chatbot"],
                height=None,
            )

            with gr.Row(elem_classes=["st-input-row"]):
                file_upload = gr.UploadButton(
                    "+",
                    file_types=[".conf", ".hocon", ".config", ".json"],
                    size="sm", scale=0, min_width=40,
                    elem_classes=["st-btn-upload"],
                )
                user_input = gr.Textbox(
                    placeholder=_t(lang, "input_placeholder"),
                    show_label=False, scale=8, lines=1,
                    elem_classes=["st-input"],
                )
                demo_btn = gr.Button(_t(lang, "demo"), variant="secondary", size="sm", scale=1, elem_classes=["st-btn-demo"])
                send_btn = gr.Button("➤", variant="primary", size="sm", scale=0, min_width=48, elem_classes=["st-btn-send"])
                stop_btn = gr.Button("■", variant="stop", size="sm", scale=0, min_width=48, visible=False, elem_classes=["st-btn-stop"])

    # ── Sidebar toggle ──
    def _close_sidebar():
        return gr.update(visible=False), gr.update(visible=True)

    def _open_sidebar():
        return gr.update(visible=True), gr.update(visible=False)

    sidebar_toggle.click(fn=_close_sidebar, outputs=[sidebar_col, sidebar_open_btn])
    sidebar_open_btn.click(fn=_open_sidebar, outputs=[sidebar_col, sidebar_open_btn])

    # ── Connect wiring ──
    load_btn.click(
        fn=_load_settings_safe,
        inputs=lang_state,
        outputs=status_box,
    )

    # ── Template selection ──
    def _on_template_select(tpl_name, lang):
        prompt = _template_to_prompt(tpl_name, lang)
        return gr.update(value=prompt)

    template_dd.change(
        fn=_on_template_select,
        inputs=[template_dd, lang_state],
        outputs=user_input,
    )

    # ── Lang switch wiring ──
    def _on_lang_change(choice):
        lang = "zh" if choice == "中文" else "en"
        return (lang, *_switch_lang(lang))

    lang_dd.change(
        fn=_on_lang_change,
        inputs=[lang_dd],
        outputs=[
            lang_state,
            mode,
            config_path,
            load_btn,
            status_box,
            user_input,
            demo_btn,
            new_chat_btn,
            history_dd,
            chatbot,
            export_btn,
            template_dd,
            rename_btn,
            delete_btn,
            rename_input,
        ],
    )

    # ── Stop handler ──
    def _handle_stop(lang):
        agent = agent_holder.get("agent")
        if agent is not None:
            agent.stop_event.set()
        c = collector_holder.get("current")
        if c and not c.done:
            c.on_event("final_answer", {"text": _t(lang, "stopped")})
        return gr.update(visible=True), gr.update(visible=False)

    stop_btn.click(
        fn=_handle_stop,
        inputs=[lang_state],
        outputs=[send_btn, stop_btn],
    )

    # ── Action wiring ──
    def _show_stop():
        return gr.update(visible=False), gr.update(visible=True)

    def _show_send():
        return gr.update(visible=True), gr.update(visible=False)

    submit_io = dict(
        fn=_handle_submit,
        inputs=[user_input, chatbot, mode, config_path, lang_state, session_state],
        outputs=[chatbot, session_state, history_dd],
    )
    def _post_submit():
        return "", gr.update(value=""), gr.update(visible=True), gr.update(visible=False)

    send_btn.click(fn=_show_stop, outputs=[send_btn, stop_btn]) \
        .then(**submit_io) \
        .then(fn=_post_submit, outputs=[user_input, template_dd, send_btn, stop_btn])
    user_input.submit(fn=_show_stop, outputs=[send_btn, stop_btn]) \
        .then(**submit_io) \
        .then(fn=_post_submit, outputs=[user_input, template_dd, send_btn, stop_btn])

    demo_btn.click(
        fn=_handle_demo,
        inputs=[user_input, chatbot, config_path, lang_state, session_state],
        outputs=[chatbot, session_state, history_dd],
    )

    # ── Sidebar wiring ──
    new_chat_btn.click(
        fn=_new_chat,
        inputs=lang_state,
        outputs=[session_state, chatbot, history_dd],
    )

    history_dd.change(
        fn=_load_history,
        inputs=[history_dd, lang_state],
        outputs=[chatbot, session_state],
    ).then(
        fn=_show_actions,
        inputs=history_dd,
        outputs=[action_row, rename_row],
    )

    delete_btn.click(
        fn=_do_delete,
        inputs=[session_state, lang_state],
        outputs=[session_state, chatbot, history_dd, action_row, rename_row],
    )

    rename_btn.click(
        fn=_open_rename,
        inputs=session_state,
        outputs=[action_row, rename_row, rename_input],
    )

    rename_ok.click(
        fn=_confirm_rename,
        inputs=[session_state, rename_input],
        outputs=[history_dd, action_row, rename_row],
    )

    rename_cancel.click(
        fn=_cancel_rename,
        outputs=[action_row, rename_row],
    )

    def _handle_export(chat_history, sid, lang):
        if not chat_history:
            raise gr.Error(_t(lang, "export_empty"))
        agent = agent_holder.get("agent")
        configs = list(agent.context.get("created_configs", [])) if agent else []
        path = _export_session(
            chat_history, sid or "export", configs,
            settings=settings_holder.get("current"),
        )
        if not path:
            raise gr.Error(_t(lang, "export_empty"))
        return path

    export_btn.click(
        fn=_handle_export,
        inputs=[chatbot, session_state, lang_state],
        outputs=export_btn,
    )

    # ── File upload handler ──
    def _handle_file_upload(file_obj):
        if file_obj is None:
            return gr.update()
        import shutil
        src = Path(file_obj.name if hasattr(file_obj, 'name') else str(file_obj))
        safe_name = re.sub(r'[^\w.\-]', '_', src.name)
        dest_dir = Path("configs")
        dest_dir.mkdir(exist_ok=True)
        dest = dest_dir / safe_name
        shutil.copy2(str(src), str(dest))
        return gr.update(value=str(dest))

    file_upload.upload(
        fn=_handle_file_upload,
        inputs=file_upload,
        outputs=config_path,
    )

    # ── Home button ──
    home_btn.click(fn=None, js="() => { window.location.href = '/'; }")

    # ── Page load ──
    app.load(fn=_on_page_load, outputs=history_dd)

    # ── Hint card click (event delegation — survives language switch) ──
    app.load(
        fn=None,
        js="""() => {
            if (document._hintDelegated) return;
            document._hintDelegated = true;
            document.addEventListener('click', e => {
                const card = e.target.closest('.st-hint-card');
                if (!card) return;
                const input = document.querySelector('.st-input textarea');
                if (input) {
                    const nativeSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLTextAreaElement.prototype, 'value').set;
                    nativeSetter.call(input, card.textContent.trim());
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });
        }""",
    )



# ------------------------------------------------------------------
# CSS — Claude-style clean design
# ------------------------------------------------------------------

_CUSTOM_CSS = """
/* ══════════════════════════════════════════
   Global — full viewport, no scroll on body
   ══════════════════════════════════════════ */
.gradio-container {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif !important;
    font-size: 11px !important;
    max-width: 100% !important;
    background: #fff !important;
    padding: 0 !important;
    height: 100vh !important;
    overflow: hidden !important;
}
.gradio-container > .main,
.gradio-container > .main > .wrap {
    height: 100vh !important;
    overflow: hidden !important;
    padding: 0 !important;
    gap: 0 !important;
    display: flex !important;
    flex-direction: column !important;
}
footer { display: none !important; }
/* Suppress Gradio default block borders globally */
.gradio-container .block {
    border: none !important;
    box-shadow: none !important;
}

/* Standalone pages (history, favorites, schema, sql review) need scrolling.
   Only the outermost .gradio-container scrolls; everything inside is visible. */
body:has(.st-history-page),
body:has(.st-review-page),
body:has(.st-uitest-page) {
    overflow: hidden !important;
}
body:has(.st-history-page) .gradio-container,
body:has(.st-review-page) .gradio-container,
body:has(.st-uitest-page) .gradio-container {
    overflow-y: auto !important;
    overflow-x: hidden !important;
    height: 100vh !important;
}
body:has(.st-history-page) .gradio-container > .main,
body:has(.st-history-page) .gradio-container > .main > .wrap,
body:has(.st-review-page) .gradio-container > .main,
body:has(.st-review-page) .gradio-container > .main > .wrap,
body:has(.st-uitest-page) .gradio-container > .main,
body:has(.st-uitest-page) .gradio-container > .main > .wrap {
    overflow: visible !important;
    height: auto !important;
    min-height: auto !important;
}
body:has(.st-uitest-page) .gradio-container > .main > .wrap {
    max-width: 1500px !important;
    width: 100% !important;
    margin: 0 auto !important;
    padding: 14px 28px 48px !important;
}

/* ══════════════════════════════════════════
   SQL Review page polish
   ══════════════════════════════════════════ */
body:has(.st-review-page) .gradio-container > .main > .wrap {
    max-width: 1500px !important;
    width: 100% !important;
    margin: 0 auto !important;
    padding: 14px 28px 48px !important;
}
/* SQL input box: fixed height with a visible vertical scrollbar
   (max_lines pins the textarea; long SQL scrolls inside the box) */
#sr-sql-box textarea {
    overflow-y: auto !important;
    scrollbar-width: thin;
}
/* Keep the SQL input visible while scrolling a long report
   (pairs with the "行 N" line-jump links) */
body:has(.st-review-page) .sr-input-col {
    position: sticky !important;
    top: 12px !important;
    align-self: flex-start !important;
}
/* Report as a card */
.gradio-container .sr-report-card {
    border: 1px solid #e5e7eb !important;
    border-radius: 10px !important;
    background: #fff !important;
    padding: 14px 18px !important;
    min-height: 320px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
}
.sr-report-card h2 { margin-top: 0 !important; }
.sr-report-card h3 { margin: 16px 0 6px !important; }
/* Report tables: bordered, striped, comfortable padding */
.sr-report-card table {
    width: 100% !important;
    border-collapse: collapse !important;
    margin: 6px 0 !important;
}
.sr-report-card th, .sr-report-card td {
    border: 1px solid #e5e7eb !important;
    padding: 6px 10px !important;
    text-align: left !important;
    vertical-align: top !important;
    line-height: 1.5 !important;
}
.sr-report-card th { background: #f3f4f6 !important; }
.sr-report-card tbody tr:nth-child(even) td { background: #fafafa !important; }
/* Line-jump links: dashed underline, no visited-color drift */
.sr-report-card a[href*="#srline-"] {
    color: #2563eb !important;
    text-decoration: none !important;
    border-bottom: 1px dashed #93c5fd !important;
    cursor: pointer !important;
}
.sr-report-card a[href*="#srline-"]:hover {
    border-bottom-style: solid !important;
}

/* ══════════════════════════════════════════════
   Sidebar — Claude-style push layout (Column)
   ══════════════════════════════════════════════ */
/* Page row: sidebar + main side by side. */
.st-page-row {
    display: flex !important;
    flex-direction: row !important;
    position: fixed !important;
    top: 0; left: 0; right: 0; bottom: 0;
    z-index: 100;
    overflow: hidden !important;
    gap: 0 !important;
    padding: 0 !important;
    flex-wrap: nowrap !important;
}
/* Left sidebar column (width adjustable via drag handle, see _SIDEBAR_RESIZE_JS).
   The Data Comparison sidebar is excluded: it has its own width + CSS resize. */
.st-sidebar:not(.st-dc-sidebar) {
    width: var(--st-sidebar-w, 260px) !important;
    min-width: var(--st-sidebar-w, 260px) !important;
    max-width: var(--st-sidebar-w, 260px) !important;
}
.st-sidebar {
    height: 100% !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    background: #f9fafb !important;
    border-right: 1px solid #e5e7eb !important;
    padding: 10px 12px !important;
    flex-shrink: 0 !important;
    gap: 4px !important;
    display: flex !important;
    flex-direction: column !important;
    flex-wrap: nowrap !important;
}
/* Direct children: full-width column layout */
.st-sidebar > * {
    width: 100% !important;
    max-width: 100% !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
    flex-shrink: 0 !important;
    border: none !important;
    box-shadow: none !important;
}
/* Re-allow horizontal layout for Row containers */
.st-sidebar .row,
.st-sidebar .st-sidebar-row,
.st-sidebar .st-filter-actions,
.st-sidebar .st-filter-confirm-row,
.st-sidebar .st-action-row,
.st-sidebar .st-rename-row {
    flex-direction: row !important;
    flex-wrap: nowrap !important;
}
/* CheckboxGroup labels: horizontal for checkbox + text */
.st-sidebar .st-table-filter label {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 0 !important;
}
.st-sidebar-toggle {
    width: 32px !important;
    min-width: 32px !important;
    max-width: 32px !important;
    height: 32px !important;
    padding: 0 !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 6px !important;
    background: #fff !important;
    font-size: 14px !important;
    cursor: pointer !important;
    margin-bottom: 6px !important;
}
.st-sidebar-toggle:hover { background: #f3f4f6 !important; }
/* Open sidebar button (visible when sidebar hidden) */
.st-sidebar-open-btn {
    width: 32px !important;
    min-width: 32px !important;
    max-width: 32px !important;
    height: 28px !important;
    padding: 0 !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 6px !important;
    background: #fff !important;
    font-size: 14px !important;
    cursor: pointer !important;
    flex-shrink: 0 !important;
}
.st-sidebar-open-btn:hover { background: #f3f4f6 !important; }
/* Data Comparison sidebar: wider, user-resizable via right-edge drag,
   horizontal scrollbar when content overflows */
.st-sidebar.st-dc-sidebar {
    /* flex-basis auto lets `width` control the size (Gradio columns default
       to flex-basis 0%, which ignores width and collapses to min-width);
       width stays non-!important so the browser's drag-resize inline style
       can override it */
    flex: 0 0 auto !important;
    width: 720px;
    min-width: 360px !important;
    max-width: 85vw !important;
    resize: horizontal !important;
    overflow-x: auto !important;
    overflow-y: auto !important;
}
.st-sidebar.st-dc-sidebar > * {
    min-width: 640px !important;
}

/* Right main content: fill remaining width, flex column to pin input at bottom */
.st-main {
    flex: 1 1 0 !important;
    min-width: 0 !important;
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
    padding: 0 !important;
    display: flex !important;
    flex-direction: column !important;
}
/* Hide Gradio's native sidebar if accidentally present */
.gradio-sidebar { display: none !important; }
/* Drag handle on the sidebar's right edge (appended to .st-page-row by JS) */
.st-sidebar-resize {
    position: absolute !important;
    top: 0 !important;
    bottom: 0 !important;
    left: calc(var(--st-sidebar-w, 260px) - 3px) !important;
    width: 7px !important;
    cursor: col-resize !important;
    z-index: 150 !important;
    background: transparent;
    transition: background 0.15s;
}
.st-sidebar-resize:hover,
.st-sidebar-resize.st-resizing {
    background: rgba(59, 130, 246, 0.35);
}
body.st-sidebar-dragging {
    cursor: col-resize !important;
    user-select: none !important;
}

/* ══════════════════════════
   Hub landing page
   ══════════════════════════ */
.st-hub {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 80vh;
    padding: 24px 16px;
    position: relative;
}
.st-hub-lang-row {
    position: absolute;
    top: 16px;
    right: 24px;
}
.st-hub-lang-row select {
    font-size: 11px;
    padding: 4px 24px 4px 10px;
    border-radius: 6px;
    border: 1px solid #e5e7eb;
    background: #f9fafb;
    height: 28px;
    cursor: pointer;
    outline: none;
}
.st-hub-lang-row select:hover { border-color: #f76707; }
.st-hub-header { text-align: center; margin-bottom: 36px; }
.st-hub-title {
    font-size: 26px;
    font-weight: 800;
    color: #1f2937;
    letter-spacing: -0.5px;
}
.st-hub-subtitle {
    font-size: 13px;
    color: #6b7280;
    margin-top: 8px;
}
.st-hub-grid {
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
    justify-content: center;
    max-width: 900px;
}
.st-hub-card {
    display: flex;
    flex-direction: column;
    width: 250px;
    padding: 22px 20px;
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    text-decoration: none !important;
    transition: transform .15s, box-shadow .15s, border-color .15s;
    cursor: pointer;
}
.st-hub-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,.08);
    border-color: #d1d5db;
}
.st-hub-card-soon {
    cursor: default;
    border-style: dashed;
    opacity: .8;
}
.st-hub-card-soon:hover { transform: none; box-shadow: none; }
.st-hub-logo {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    color: #fff;
    font-size: 15px;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 14px;
    letter-spacing: -0.5px;
}
.st-hub-card-title {
    font-size: 14px;
    font-weight: 700;
    color: #1f2937;
    margin-bottom: 6px;
}
.st-hub-zh {
    font-size: 11px;
    font-weight: 500;
    color: #9ca3af;
}
.st-hub-card-desc {
    font-size: 11px;
    color: #6b7280;
    line-height: 1.6;
    flex-grow: 1;
}
.st-hub-enter {
    margin-top: 14px;
    font-size: 11px;
    font-weight: 600;
}
/* ══════════════════════════════════════════
   Chatbot — fill remaining height exactly
   ══════════════════════════════════════════ */
.st-chatbot {
    border: none !important;
    background: #fff !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    overflow-y: auto !important;
    padding: 0 !important;
    margin: 0 !important;
    flex: 1 1 0 !important;
    min-height: 0 !important;
}
.st-chart {
    max-height: 280px !important;
    overflow: hidden !important;
    flex: none !important;
}
.st-chart img, .st-chart canvas, .st-chart svg {
    max-height: 260px !important;
    width: auto !important;
    margin: 0 auto !important;
    display: block !important;
}
.st-chatbot .message {
    font-size: 11px !important;
    line-height: 1.6 !important;
    padding: 6px 20px !important;
}
/* ── User message: right-aligned with left space ── */
.st-chatbot .user-row {
    margin-left: 22% !important;
    margin-top: 14px !important;
    margin-bottom: 14px !important;
    background: #fff7ed !important;
    border: 1px solid #fed7aa !important;
    border-radius: 16px 16px 4px 16px !important;
    padding: 8px 14px !important;
}
.st-chatbot .user-row .message {
    padding: 0 !important;
}
.st-chatbot .message code {
    font-size: 10px !important;
    background: #f3f4f6 !important;
    padding: 1px 4px !important;
    border-radius: 3px !important;
}
.st-chatbot .message pre {
    background: #1e1e2e !important;
    color: #cdd6f4 !important;
    padding: 8px 12px !important;
    border-radius: 6px !important;
    font-size: 10px !important;
    margin: 4px 0 !important;
    overflow-x: auto !important;
}

/* ── Inline download buttons inside chat messages ── */
.st-dl-btns {
    display: flex;
    gap: 8px;
    margin-top: 8px;
    flex-wrap: wrap;
}
.st-dl-btns a:hover {
    background: var(--background-fill-primary, #eee) !important;
}

/* ── Input row — pinned to bottom of viewport ── */
.st-input-row,
.st-input-row.row {
    padding: 6px 20px 10px !important;
    gap: 6px !important;
    align-items: flex-end !important;
    border-top: 1px solid #f0f0f0;
    flex: 0 0 auto !important;
    flex-shrink: 0 !important;
    flex-grow: 0 !important;
    height: auto !important;
    max-height: 60px !important;
    min-height: 44px !important;
    background: #fff !important;
    overflow: visible !important;
    flex-direction: row !important;
}
.st-input textarea {
    border-radius: 20px !important;
    padding: 8px 14px !important;
    font-size: 11px !important;
    border: 1px solid #d1d5db !important;
    background: #fff !important;
    box-shadow: 0 1px 3px rgba(0,0,0,.04) !important;
    transition: border-color .15s, box-shadow .15s !important;
}
.st-input textarea:focus {
    border-color: #f76707 !important;
    box-shadow: 0 0 0 2px rgba(247,103,7,.12) !important;
}

/* ── Buttons ── */
.st-btn-send {
    border-radius: 50% !important;
    width: 34px !important;
    height: 34px !important;
    min-width: 34px !important;
    max-width: 34px !important;
    background: #f76707 !important;
    color: #fff !important;
    border: none !important;
    font-size: 14px !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    flex-shrink: 0 !important;
}
.st-btn-send:hover { background: #e8590c !important; }
.st-btn-stop {
    border-radius: 50% !important;
    width: 34px !important;
    height: 34px !important;
    min-width: 34px !important;
    max-width: 34px !important;
    background: #dc2626 !important;
    color: #fff !important;
    border: none !important;
    font-size: 12px !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    flex-shrink: 0 !important;
}
.st-btn-stop:hover { background: #b91c1c !important; }
.st-btn-upload {
    border-radius: 50% !important;
    width: 34px !important;
    height: 34px !important;
    min-width: 34px !important;
    max-width: 34px !important;
    background: #f3f4f6 !important;
    color: #374151 !important;
    border: 1px solid #d1d5db !important;
    font-size: 16px !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    flex-shrink: 0 !important;
}
.st-btn-upload:hover {
    background: #e5e7eb !important;
    border-color: #f76707 !important;
    color: #f76707 !important;
}
.st-btn-demo {
    background: #fff !important;
    border: 1.5px solid #e5e7eb !important;
    color: #374151 !important;
    font-weight: 500 !important;
    border-radius: 20px !important;
    font-size: 10px !important;
    height: 34px !important;
    padding: 0 12px !important;
}
.st-btn-demo:hover {
    border-color: #f76707 !important;
    color: #f76707 !important;
    background: #fffbf5 !important;
}

/* ── Placeholder (empty state) ── */
.st-empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 16px 30px;
    color: #6b7280;
}
.st-empty-logo {
    font-size: 22px;
    font-weight: 800;
    background: #f76707;
    color: #fff;
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 16px;
    letter-spacing: -1px;
}
.st-empty-title {
    font-size: 16px;
    font-weight: 600;
    color: #1f2937;
    margin-bottom: 20px;
}
.st-empty-hints {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: center;
    max-width: 540px;
}
.st-hint-card {
    padding: 9px 14px;
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    font-size: 13px;
    color: #4b5563;
    cursor: pointer;
    transition: border-color .15s;
}
.st-hint-card:hover {
    border-color: #f76707;
    color: #f76707;
}
.st-docs-link {
    display: inline-block;
    margin-top: 16px;
    padding: 7px 16px;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    font-size: 11px;
    color: #6b7280;
    text-decoration: none;
    transition: border-color .15s, color .15s, background .15s;
}
.st-docs-link:hover {
    border-color: #f76707;
    color: #f76707;
    background: #fffbf5;
}

/* ── Sidebar ── */
.st-new-chat-btn {
    width: 100% !important;
    margin-bottom: 6px !important;
    border-radius: 8px !important;
}
.st-action-row {
    gap: 6px !important;
    margin-top: 4px !important;
}
.st-action-btn {
    font-size: 10px !important;
    border-radius: 6px !important;
    padding: 3px 6px !important;
}
.st-rename-row {
    gap: 4px !important;
    margin-top: 4px !important;
    align-items: flex-end !important;
}
.st-rename-input textarea {
    font-size: 10px !important;
    padding: 4px 8px !important;
    border-radius: 6px !important;
}
.st-rename-ok, .st-rename-cancel {
    font-size: 12px !important;
    border-radius: 6px !important;
    min-width: 32px !important;
    height: 30px !important;
}
.st-delete-btn {
    border-radius: 6px !important;
}
.st-history-dd { font-size: 10px !important; }
.st-connect-btn {
    width: 100% !important;
    border-radius: 8px !important;
    margin-top: 2px !important;
}
.st-sidebar-row {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 6px !important;
    width: 100% !important;
}
.st-sidebar-row > * {
    flex: 1 !important;
    min-width: 0 !important;
}
/* Fix Dropdown arrow blown up by sidebar flex overrides */
.st-sidebar svg[class*="dropdown-arrow"] {
    width: 18px !important;
    height: 18px !important;
    min-width: 18px !important;
    min-height: 18px !important;
    max-width: 18px !important;
    max-height: 18px !important;
}
.st-sidebar [class*="icon-wrap"] {
    width: auto !important;
    min-width: 0 !important;
    max-width: none !important;
    flex-shrink: 0 !important;
}
.st-sidebar [class*="secondary-wrap"] {
    flex-direction: row !important;
    align-items: center !important;
    width: 100% !important;
}
.st-filter-accordion {
    margin-top: 4px !important;
    overflow: hidden !important;
    width: 100% !important;
}
.st-filter-accordion [class*="label-wrap"] {
    padding: 4px 8px !important;
    min-height: 0 !important;
    font-size: 12px !important;
    line-height: 1.3 !important;
    background: #f9fafb !important;
    border: none !important;
    box-shadow: none !important;
    gap: 4px !important;
}
.st-filter-accordion [class*="label-wrap"] span {
    font-size: 12px !important;
    font-weight: 500 !important;
    line-height: 1.3 !important;
}
.st-filter-accordion [class*="label-wrap"] span[class*="icon"] {
    font-size: 10px !important;
}
.st-table-search textarea {
    width: 100% !important;
    font-size: 12px !important;
    padding: 4px 8px !important;
    min-height: 28px !important;
    border-radius: 6px !important;
}
.st-table-search { margin-bottom: 2px !important; }
.st-table-filter {
    width: 100% !important;
    max-height: 200px !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    border: 1px solid #f0f0f0 !important;
    border-radius: 6px !important;
    padding: 4px 6px !important;
}
.st-table-filter .wrap {
    flex-direction: column !important;
    flex-wrap: nowrap !important;
    gap: 1px !important;
    width: 100% !important;
}
.st-table-filter label {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    min-width: 0 !important;
    font-size: 12px !important;
    line-height: 1.5 !important;
    padding: 2px 0 !important;
    cursor: pointer !important;
}
.st-table-filter label span {
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
    min-width: 0 !important;
}
.st-table-filter label:hover { background: #f5f5f5 !important; border-radius: 4px !important; }
.st-table-filter input[type="checkbox"] {
    width: 14px !important; height: 14px !important;
    min-width: 14px !important;
    flex-shrink: 0 !important;
    margin-right: 6px !important;
}
.st-filter-actions {
    gap: 4px !important;
    flex-wrap: nowrap !important;
}
.st-filter-act-btn {
    font-size: 11px !important;
    padding: 2px 6px !important;
    min-width: 0 !important;
    border-radius: 4px !important;
    flex: 1 !important;
}
.st-filter-confirm-row {
    gap: 4px !important;
    margin-top: 2px !important;
    flex-wrap: nowrap !important;
}
.st-filter-confirm-btn, .st-filter-cancel-btn {
    font-size: 12px !important;
    padding: 4px 10px !important;
    border-radius: 6px !important;
    min-width: 0 !important;
    flex: 1 !important;
}
.st-sidebar-control label {
    font-size: 10px !important;
    font-weight: 600 !important;
    color: #6b7280 !important;
}
.st-sidebar-control input,
.st-sidebar-control select { font-size: 10px !important; }
.st-sidebar-status input { font-size: 10px !important; }

/* ── Top bar with language switcher ── */
.st-topbar-row,
.st-topbar-row.row {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    justify-content: flex-end !important;
    padding: 6px 16px !important;
    margin: 0 !important;
    gap: 8px !important;
    min-height: 36px !important;
    max-height: 36px !important;
    height: 36px !important;
    flex: 0 0 36px !important;
    background: #fff !important;
    border-bottom: 1px solid #f0f0f0 !important;
    overflow: visible !important;
    flex-wrap: nowrap !important;
}
.st-topbar-spacer {
    flex: 1 !important;
}
.st-lang-dd {
    max-width: 140px !important;
    min-width: 120px !important;
}
.st-lang-dd select,
.st-lang-dd input {
    font-size: 10px !important;
    padding: 3px 24px 3px 8px !important;
    border-radius: 6px !important;
    border: 1px solid #e5e7eb !important;
    background: #f9fafb !important;
    height: 26px !important;
    cursor: pointer !important;
}
.st-lang-dd select:hover,
.st-lang-dd input:hover {
    border-color: #f76707 !important;
}

/* ── Home button in topbar ── */
.st-home-btn {
    min-width: 32px !important;
    max-width: 32px !important;
    height: 28px !important;
    padding: 0 !important;
    font-size: 14px !important;
    border-radius: 6px !important;
    border: 1px solid #e5e7eb !important;
    background: #f9fafb !important;
    cursor: pointer !important;
    flex-shrink: 0 !important;
}
.st-home-btn:hover {
    border-color: #f76707 !important;
    background: #fff7ed !important;
}


/* ── History / Favorites page ── */
.st-history-page {
    padding: 16px 28px !important;
    max-width: 1400px !important;
    margin: 0 auto !important;
    overflow: visible !important;
    height: auto !important;
}
.st-history-page h2 {
    font-size: 16px !important;
    font-weight: 700 !important;
    color: #111827 !important;
    margin: 0 0 4px !important;
}
.st-hist-toolbar {
    gap: 6px !important;
    margin-bottom: 6px !important;
}
.st-hist-btn {
    min-width: 0 !important;
    padding: 3px 10px !important;
    font-size: 11px !important;
    border-radius: 6px !important;
}
.st-hist-sel-info {
    min-height: 0 !important;
    margin: 0 0 2px !important;
}
.st-hist-sel-info p {
    font-size: 11px !important;
    color: #6b7280 !important;
    margin: 0 !important;
}
.st-fav-search-row { margin-bottom: 4px !important; }
.st-fav-rename-row { margin-bottom: 4px !important; }
.st-fav-table,
.st-hist-table {
    overflow: visible !important;
}
.st-fav-table > div,
.st-hist-table > div,
.st-history-page .wrap,
.st-history-page .table-wrap {
    overflow: visible !important;
    max-height: none !important;
}
.st-history-page table {
    font-size: 12px !important;
    width: 100% !important;
    border-collapse: collapse !important;
}
.st-history-page th {
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.3px !important;
    color: #9ca3af !important;
    background: #f9fafb !important;
    padding: 6px 10px !important;
    white-space: nowrap !important;
    border-bottom: 2px solid #e5e7eb !important;
    position: sticky !important;
    top: 0 !important;
    z-index: 2 !important;
}
.st-history-page td {
    padding: 6px 10px !important;
    border-bottom: 1px solid #f3f4f6 !important;
    vertical-align: top !important;
    line-height: 1.4 !important;
    color: #374151 !important;
}
.st-history-page tr:hover td {
    background: #f0f7ff !important;
    cursor: pointer;
}
.st-history-page td:nth-child(1) {
    color: #9ca3af !important;
    font-size: 11px !important;
}
.st-history-page td:nth-child(2) {
    color: #6b7280 !important;
    font-size: 11px !important;
    white-space: nowrap !important;
}

/* ── SQL column: show full text, wrap naturally ── */
.st-fav-table td:nth-child(4),
.st-hist-table td:nth-child(6) {
    font-family: 'SF Mono', 'Consolas', 'Monaco', monospace !important;
    font-size: 11px !important;
    color: #6b7280 !important;
    white-space: pre-wrap !important;
    word-break: break-word !important;
}

/* ── Hide Gradio block borders inside history/favorites pages ── */
.st-history-page > *,
.st-history-page > * > *,
.st-history-page [class*="block"],
.st-history-page [class*="panel"],
.st-history-page [class*="form"],
.st-history-page [class*="padded"] {
    border: none !important;
    box-shadow: none !important;
}
.st-history-page h3 {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #374151 !important;
    margin: 8px 0 4px !important;
}

/* ── Responsive sizing ── */
button { font-size: 10px !important; }
label { font-size: 10px !important; }

"""


def _kill_port(port: int) -> bool:
    """Kill whatever process is listening on *port*. Returns True if killed."""
    import subprocess, sys
    if sys.platform != "win32":
        r = subprocess.run(
            ["lsof", "-ti", f":{port}"], capture_output=True, text=True,
        )
        for pid in r.stdout.split():
            subprocess.run(["kill", "-9", pid])
        return bool(r.stdout.strip())
    r = subprocess.run(
        ["netstat", "-ano"], capture_output=True, text=True,
    )
    for line in r.stdout.splitlines():
        parts = line.split()
        # netstat -ano: Proto  Local Address  Foreign Address  State  PID
        if len(parts) >= 5 and parts[3] == "LISTENING" and parts[1].endswith(f":{port}"):
            subprocess.run(["taskkill", "/F", "/PID", parts[4]],
                           capture_output=True)
            return True
    return False


def _port_has_listener(port: int) -> bool:
    """Check if a process is actually LISTENING on *port* (not TIME_WAIT)."""
    import subprocess, sys
    if sys.platform == "win32":
        r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
        return any(f":{port}" in ln and "LISTENING" in ln for ln in r.stdout.splitlines())
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def launch_app(app: gr.Blocks, port: int = 7860, host: str = "127.0.0.1", share: bool = False, api: bool = False) -> None:
    if _port_has_listener(port):
        import os
        if os.getenv("SEATUNNEL_UI_KILL_PORT", "").lower() in ("1", "true", "yes"):
            print(f"[ui] Port {port} in use — killing old process (SEATUNNEL_UI_KILL_PORT is set)...")
            _kill_port(port)
            import time; time.sleep(0.5)
        else:
            raise SystemExit(
                f"[ui] Port {port} is already in use. Stop the process using it, "
                f"choose another port, or set SEATUNNEL_UI_KILL_PORT=1 to kill it automatically."
            )

    if api:
        from .text2sql.api import router as t2s_api_router
        from .sql_review.api import router as sql_review_api_router
        fastapi_app = app.app
        fastapi_app.include_router(t2s_api_router)
        fastapi_app.include_router(sql_review_api_router)

    app.launch(
        server_name=host,
        server_port=port,
        share=share,
        inbrowser=True,
        css=_CUSTOM_CSS,
    )


def main() -> None:
    app = create_ui()
    launch_app(app)


if __name__ == "__main__":
    main()
