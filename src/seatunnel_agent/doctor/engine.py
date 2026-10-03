# -*- coding: utf-8 -*-
"""Doctor agent — "the UI won't start": read-only diagnosis loop.

Tools are strictly read-only (ports, installed packages, LLM config with
secrets masked, log tails) — the doctor diagnoses and prescribes shell
commands for the HUMAN to run, it never executes fixes itself.  Without an
API key it degrades to a deterministic full check-up report.
"""

from __future__ import annotations

import os
import re
import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..agent_core import Step, ToolLoopAgent, ToolSpec
from ..config import Settings

_KEY_PACKAGES = ("gradio", "fastapi", "sqlglot", "matplotlib", "anthropic",
                 "openai", "pyyaml", "playwright", "click", "pyhocon")
_TAIL_LINES = 80

_SYSTEM = """\
You are an environment doctor for the seatunnel-agent platform (a Python
Gradio app with CLI and REST surfaces).

Given a user complaint, investigate with the read-only tools (ports,
installed packages, LLM config, log tails), then answer with:
1. the most likely root cause,
2. the exact commands the USER should run to fix it (you never run fixes),
3. how to verify the fix worked.
Answer in the user's language. If the evidence is inconclusive, say what to
check next instead of guessing.
"""


def check_port(port: int = 7860) -> str:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=1):
            return f"port {port}: LISTENING (something already runs there)"
    except OSError:
        return f"port {port}: free"


def check_env() -> str:
    from ..dep_check import installed_lookup
    lines = [f"python {sys.version.split()[0]} @ {sys.executable}"]
    for name in _KEY_PACKAGES:
        info = installed_lookup(name)
        lines.append(f"{name}: {info[0] if info else 'NOT INSTALLED'}")
    return "\n".join(lines)


def check_llm_config() -> str:
    from ..settings_store import mask_secret
    key = os.getenv("API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", "")
    return "\n".join([
        f"LLM_PROVIDER = {os.getenv('LLM_PROVIDER', 'anthropic')}",
        f"MODEL_NAME   = {os.getenv('MODEL_NAME', '(default)')}",
        f"LLM_BASE_URL = {os.getenv('LLM_BASE_URL', '') or '(unset)'}",
        f"API_KEY      = {mask_secret(key) or '(unset)'}",
    ])


def list_logs(logs_dir: str = "logs") -> str:
    root = Path(logs_dir)
    if not root.is_dir():
        return f"(no {logs_dir}/ directory)"
    rows = []
    for f in sorted(root.glob("*")):
        if f.is_file():
            rows.append(f"{f.name}\t{f.stat().st_size} bytes")
    return "\n".join(rows) or "(empty)"


# files the doctor must never read: they exist to hold secrets, and the
# page is reachable from the web UI
_SENSITIVE_NAME = re.compile(
    r"\.env|credential|secret|token|apikey|api_key|llm_settings|\.pem|"
    r"id_rsa|\.p12|\.keystore", re.I)


def _redact(line: str) -> str:
    """Mask anything that looks like a credential before it reaches the
    model/UI — reuses the secret-scan rule catalog."""
    from ..secret_scan.rules import RULES
    for rule in RULES:
        line = rule.pattern.sub("«masked»", line)
    return line


def read_log_tail(path: str, lines: int = _TAIL_LINES) -> str:
    p = Path(path)
    if _SENSITIVE_NAME.search(p.name):
        return (f"(refused: {p.name} looks like a credentials file — "
                "the doctor only reads logs)")
    if not p.is_file():
        return f"(not a file: {path})"
    try:
        content = p.read_text(encoding="utf-8",
                              errors="replace").splitlines()
    except OSError as exc:
        return f"(read failed: {exc})"
    lines = max(1, min(int(lines), 200))
    return "\n".join(_redact(ln) for ln in content[-lines:]) or "(empty)"


def build_tools() -> list[ToolSpec]:
    s = {"type": "string"}
    n = {"type": "integer"}
    return [
        ToolSpec("check_port", "检查本机端口是否已被监听(默认 7860)。",
                 {"type": "object", "properties": {"port": n},
                  "required": []}, check_port),
        ToolSpec("check_env", "Python 版本与关键依赖的安装情况。",
                 {"type": "object", "properties": {}, "required": []},
                 check_env),
        ToolSpec("check_llm_config", "当前 LLM 配置(密钥已脱敏)。",
                 {"type": "object", "properties": {}, "required": []},
                 check_llm_config),
        ToolSpec("list_logs", "列出 logs/ 目录下的日志文件。",
                 {"type": "object", "properties": {"logs_dir": s},
                  "required": []}, list_logs),
        ToolSpec("read_log_tail", "读取某个日志文件的末尾(最多 200 行)。",
                 {"type": "object",
                  "properties": {"path": s, "lines": n},
                  "required": ["path"]}, read_log_tail),
    ]


@dataclass
class DoctorResult:
    reply: str
    steps: list[Step] = field(default_factory=list)
    deterministic: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"reply": self.reply, "deterministic": self.deterministic,
                "steps": [s.to_dict() for s in self.steps]}


def _checkup_markdown(lang: str = "zh") -> str:
    zh = not (lang or "").lower().startswith("en")
    title = "## 环境体检(确定性)" if zh else "## Environment check-up (deterministic)"
    note = ("> 未配置 LLM — 以下是全量检查结果;配置 API key 后可用自然语言"
            "描述症状做针对性诊断。" if zh else
            "> No LLM configured — full check-up below; with an API key you "
            "can describe the symptom in natural language instead.")
    return "\n".join([
        title, "", note, "",
        "### Ports", "```", check_port(7860), check_port(7861), "```",
        "### Packages", "```", check_env(), "```",
        "### LLM config", "```", check_llm_config(), "```",
        "### Logs", "```", list_logs(), "```",
    ])


def diagnose(complaint: str, settings: Settings | None = None,
             lang: str = "zh", max_steps: int = 6, client: Any = None,
             on_step=None) -> DoctorResult:
    """LLM loop when configured; deterministic full check-up otherwise."""
    if settings is None and client is None:
        return DoctorResult(reply=_checkup_markdown(lang),
                            deterministic=True)
    agent = ToolLoopAgent(settings or Settings(api_key="injected"),
                          tools=build_tools(), system_prompt=_SYSTEM,
                          agent_name="doctor", max_steps=max_steps,
                          client=client)
    loop = agent.run(complaint, on_step=on_step)
    return DoctorResult(reply=loop.reply, steps=loop.steps)
