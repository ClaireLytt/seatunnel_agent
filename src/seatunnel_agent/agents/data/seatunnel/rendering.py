"""Non-Gradio rendering helpers for the SeaTunnel page.

Extracted verbatim from the legacy Gradio ui.py on its retirement:
the event->markdown chat formatter, the backend-facing i18n strings,
and the demo-mode scripts/config used by the /api/seatunnel/demo SSE
endpoint.

I18N holds only keys the backend itself renders (mode labels, SSE
error/stop messages, demo wording). The legacy page's UI-chrome wording
lives as inline literals in tests/test_seatunnel_i18n.py, which checks
the React i18n.ts against it (react_migration.md item 6: prune
UI-chrome keys on retirement; parity truth moves to the test).
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

# ------------------------------------------------------------------
# i18n (backend-rendered strings only; wording verbatim from legacy ui.py)
# ------------------------------------------------------------------

I18N: dict[str, dict[str, str]] = {
    "en": {
        "mode_nl": "Natural Language",
        "mode_run": "Run Config",
        "mode_validate": "Validate Config",
        "mode_diagnose": "Diagnose Log",
        "no_settings": "Settings not loaded. Click **Connect** first and make sure `.env` is configured.",
        "stopped": "Agent stopped by user.",
        "demo_validate_done": "**Validation complete!** Config file `{path}` has correct syntax with required source and sink sections.",
        "demo_general_done": (
            "**Config generated and validated!**\n\n"
            "Saved to `{path}`:\n"
            "- **Source**: FakeSource (5 fake rows, fields: id/name/age)\n"
            "- **Sink**: Console (print to stdout)\n\n"
            "Ready to run if SeaTunnel is installed."
        ),
    },
    "zh": {
        "mode_nl": "自然语言描述",
        "mode_run": "运行配置文件",
        "mode_validate": "验证配置",
        "mode_diagnose": "诊断日志",
        "no_settings": "未加载配置。请先点击 **连接**，确保 `.env` 已配置。",
        "stopped": "已被用户中断。",
        "demo_validate_done": "**验证完成！** 配置文件 `{path}` 语法正确，包含必要的 source 和 sink 部分。",
        "demo_general_done": (
            "**配置已生成并验证通过！**\n\n"
            "配置文件保存在 `{path}`，包含：\n"
            "- **Source**: FakeSource（生成 5 行假数据，字段 id/name/age）\n"
            "- **Sink**: Console（输出到控制台）\n\n"
            "如果安装了 SeaTunnel，可以直接运行此配置。"
        ),
    },
}


def translate(lang: str, key: str) -> str:
    return I18N.get(lang, I18N["en"]).get(key, I18N["en"].get(key, key))


# ------------------------------------------------------------------
# Demo mode scripts
# ------------------------------------------------------------------

DEMO_STEPS: dict[str, list[dict[str, Any]]] = {
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

DEMO_CONFIG = """\
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

TOOL_EMOJI = {
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


def format_events_as_chat(events: list[dict[str, Any]], start_time: float | None = None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    delta_buffer: list[str] = []

    def _flush_delta() -> None:
        # No " ▌" suffix: the legacy Gradio formatter baked the streaming
        # cursor into flushed history (a rendering bug); the live cursor now
        # lives only on the React page's in-flight bubble (Chat.tsx).
        if delta_buffer:
            accumulated = "".join(delta_buffer)
            if accumulated.strip():
                messages.append({"role": "assistant", "content": accumulated})
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
            emoji = TOOL_EMOJI.get(name, "\U0001f527")
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

