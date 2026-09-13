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

from .config import Settings, load_settings
from .agent import SeaTunnelAgent
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
        time.sleep(0.35)

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

    def snapshot(self) -> list[dict[str, Any]]:
        with self.lock:
            return list(self.events)


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
        collector.wait_for_event(timeout=0.3)
        events = collector.snapshot()
        if len(events) > prev_count:
            prev_count = len(events)
            yield chat_history + [{"role": "user", "content": user_message}] + _format_events_as_chat(events, start_time)
    thread.join(timeout=5)
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
  <a href="https://github.com/ClaireLytt/seatunnel_agent#readme"
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


def create_ui() -> gr.Blocks:
    settings_holder: dict[str, Settings | None] = {"current": None}
    agent_holder: dict[str, SeaTunnelAgent | None] = {"agent": None}
    collector_holder: dict[str, EventCollector | None] = {"current": None}

    lang = "en"

    # ── Callbacks ──

    def _load_settings_safe(lang):
        try:
            settings_holder["current"] = load_settings()
            s = settings_holder["current"]
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
        )

    # ── Layout ──

    with gr.Blocks(
        title="SeaTunnel Agent",
        fill_height=True,
        fill_width=True,
        css=_CUSTOM_CSS,
    ) as app:

        lang_state = gr.State("en")
        session_state = gr.State("")

        # ── Sidebar: history + settings ──
        with gr.Sidebar(
            label="SeaTunnel Agent",
            position="left",
            open=True,
            width=280,
        ):
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
                rename_btn = gr.Button(
                    "✏ Rename",
                    size="sm",
                    scale=1,
                    elem_classes=["st-action-btn"],
                )
                delete_btn = gr.Button(
                    "✕ Delete",
                    variant="stop",
                    size="sm",
                    scale=1,
                    elem_classes=["st-action-btn"],
                )
            with gr.Row(visible=False, elem_classes=["st-rename-row"]) as rename_row:
                rename_input = gr.Textbox(
                    show_label=False,
                    placeholder="New name...",
                    scale=3,
                    lines=1,
                    elem_classes=["st-rename-input"],
                )
                rename_ok = gr.Button(
                    "✓",
                    size="sm",
                    scale=0,
                    min_width=36,
                    elem_classes=["st-rename-ok"],
                )
                rename_cancel = gr.Button(
                    "✕",
                    size="sm",
                    scale=0,
                    min_width=36,
                    elem_classes=["st-rename-cancel"],
                )

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
            load_btn = gr.Button(
                _t(lang, "connect"),
                variant="secondary",
                size="sm",
                elem_classes=["st-connect-btn"],
            )
            status_box = gr.Textbox(
                label=_t(lang, "status"),
                interactive=False,
                value=_t(lang, "status_default"),
                elem_classes=["st-sidebar-status"],
            )
            export_btn = gr.DownloadButton(
                _t(lang, "export"),
                variant="secondary",
                size="sm",
                elem_classes=["st-connect-btn"],
            )

        # ── Main area ──
        with gr.Row(elem_classes=["st-topbar-row"]):
            gr.HTML('<div class="st-topbar-spacer"></div>')
            lang_dd = gr.Dropdown(
                choices=["English", "中文"],
                value="English",
                show_label=False,
                container=False,
                min_width=140,
                elem_classes=["st-lang-dd"],
            )

        chatbot = gr.Chatbot(
            scale=1,
            show_label=False,
            placeholder=_build_placeholder(lang),
            layout="panel",
            buttons=["copy"],
            elem_classes=["st-chatbot"],
        )

        with gr.Row(elem_classes=["st-input-row"]):
            file_upload = gr.UploadButton(
                "+",
                file_types=[".conf", ".hocon", ".config", ".json"],
                size="sm",
                scale=0,
                min_width=40,
                elem_classes=["st-btn-upload"],
            )
            user_input = gr.Textbox(
                placeholder=_t(lang, "input_placeholder"),
                show_label=False,
                scale=8,
                lines=1,
                elem_classes=["st-input"],
            )
            demo_btn = gr.Button(
                _t(lang, "demo"),
                variant="secondary",
                size="sm",
                scale=1,
                elem_classes=["st-btn-demo"],
            )
            send_btn = gr.Button(
                "➤",
                variant="primary",
                size="sm",
                scale=0,
                min_width=48,
                elem_classes=["st-btn-send"],
            )
            stop_btn = gr.Button(
                "■",
                variant="stop",
                size="sm",
                scale=0,
                min_width=48,
                visible=False,
                elem_classes=["st-btn-stop"],
            )

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
            ],
        )

        # ── Stop handler ──
        def _handle_stop(lang):
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

        # ── Hint card click → fill input ──
        chatbot.change(
            fn=None,
            js="""() => {
                document.querySelectorAll('.st-hint-card').forEach(card => {
                    if (!card.dataset.bound) {
                        card.dataset.bound = '1';
                        card.style.cursor = 'pointer';
                        card.addEventListener('click', () => {
                            const input = document.querySelector('.st-input textarea');
                            if (input) {
                                const nativeSetter = Object.getOwnPropertyDescriptor(
                                    window.HTMLTextAreaElement.prototype, 'value').set;
                                nativeSetter.call(input, card.textContent.trim());
                                input.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                        });
                    }
                });
            }""",
        )

        # ── Page load ──
        app.load(fn=_on_page_load, outputs=history_dd)

    return app


# ------------------------------------------------------------------
# CSS — Claude-style clean design
# ------------------------------------------------------------------

_CUSTOM_CSS = """
/* ── Global ── */
.gradio-container {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif !important;
    font-size: 11px !important;
    max-width: 100% !important;
    background: #fff !important;
    padding: 0 !important;
    height: 100vh !important;
    overflow: hidden !important;
}
.gradio-container > .main > .wrap {
    height: 100vh !important;
    overflow: hidden !important;
}
footer { display: none !important; }

/* ── Chatbot — borderless, full width, fill viewport ── */
.st-chatbot {
    border: none !important;
    background: #fff !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    flex-grow: 1 !important;
    min-height: 0 !important;
    overflow-y: auto !important;
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

/* ── Input row — full width with padding ── */
.st-input-row {
    padding: 4px 20px 10px !important;
    gap: 6px !important;
    align-items: flex-end !important;
    border-top: 1px solid #f0f0f0;
    flex-shrink: 0 !important;
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
    padding: 7px 12px;
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    font-size: 11px;
    color: #4b5563;
    cursor: default;
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
.st-sidebar-control label {
    font-size: 10px !important;
    font-weight: 600 !important;
    color: #6b7280 !important;
}
.st-sidebar-control input,
.st-sidebar-control select { font-size: 10px !important; }
.st-sidebar-status input { font-size: 10px !important; }

/* ── Top bar with language switcher (floating) ── */
.st-topbar-row {
    position: absolute !important;
    top: 8px !important;
    right: 16px !important;
    z-index: 100 !important;
    padding: 0 !important;
    gap: 0 !important;
    min-height: 0 !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    flex-wrap: nowrap !important;
    width: auto !important;
}
.st-topbar-spacer {
    display: none !important;
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

/* ── Upload button (inline "+") ── */
.st-btn-upload {
    border-radius: 50% !important;
    width: 34px !important;
    height: 34px !important;
    min-width: 34px !important;
    max-width: 34px !important;
    font-size: 16px !important;
    padding: 0 !important;
    flex-shrink: 0 !important;
}

/* ── Responsive sizing ── */
button { font-size: 10px !important; }
label { font-size: 10px !important; }

"""


def launch_app(app: gr.Blocks, port: int = 7860, host: str = "127.0.0.1", share: bool = False) -> None:
    app.launch(
        server_name=host,
        server_port=port,
        share=share,
        inbrowser=True,
    )


def main() -> None:
    app = create_ui()
    launch_app(app)


if __name__ == "__main__":
    main()
