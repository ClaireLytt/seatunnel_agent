# -*- coding: utf-8 -*-
"""Doctor agent: read-only tools, deterministic fallback, LLM loop, CLI."""

from __future__ import annotations

import socketserver
import threading

from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.config import Settings
from seatunnel_agent.doctor import diagnose
from seatunnel_agent.doctor.engine import (
    check_env,
    check_llm_config,
    check_port,
    read_log_tail,
)
from seatunnel_agent.llm import LLMResponse, ToolCall

SETTINGS = Settings(api_key="sk-test")


def _text(reply):
    return LLMResponse(wants_tool_use=False, tool_calls=[], thinking_text="",
                       reply_text=reply, raw_content={"f": 1}, usage={})


def _tool(name, inp, cid="c1"):
    return LLMResponse(wants_tool_use=True,
                       tool_calls=[ToolCall(id=cid, name=name, input=inp)],
                       thinking_text="", reply_text="",
                       raw_content={"f": 1}, usage={})


class ScriptedClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.tool_outputs = []

    def chat(self, system, messages):
        return self.responses.pop(0) if self.responses else _text("done")

    def append_assistant(self, raw):
        return {"role": "assistant", "content": raw}

    def build_tool_result_message(self, trs):
        self.tool_outputs.extend(t["content"] for t in trs)
        return {"role": "user", "content": trs}


class TestTools:
    def test_check_port_listening_and_free(self):
        with socketserver.TCPServer(("127.0.0.1", 0),
                                    socketserver.BaseRequestHandler) as srv:
            port = srv.server_address[1]
            threading.Thread(target=srv.handle_request,
                             daemon=True).start()
            assert "LISTENING" in check_port(port)
        assert "free" in check_port(1)  # port 1 is never listening locally

    def test_check_env_lists_packages(self):
        out = check_env()
        assert "python" in out and "gradio:" in out
        assert "NOT INSTALLED" not in out.split("gradio:")[1].splitlines()[0]

    def test_llm_config_masks_key(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "sk-super-secret-value-123456")
        out = check_llm_config()
        assert "sk-super-secret-value-123456" not in out
        assert "API_KEY" in out

    def test_read_log_tail(self, tmp_path):
        f = tmp_path / "a.log"
        f.write_text("\n".join(f"line{i}" for i in range(300)),
                     encoding="utf-8")
        out = read_log_tail(str(f), lines=10)
        assert out.splitlines() == [f"line{i}" for i in range(290, 300)]
        assert "not a file" in read_log_tail(str(tmp_path / "nope.log"))


class TestDiagnose:
    def test_deterministic_without_key(self):
        result = diagnose("ui 起不来", settings=None, lang="zh")
        assert result.deterministic
        assert "环境体检" in result.reply and "Ports" in result.reply

    def test_llm_loop(self):
        client = ScriptedClient([
            _tool("check_port", {"port": 7860}),
            _tool("check_env", {}),
            _text("根因:端口被占用。修复:taskkill …;验证:重启 UI。"),
        ])
        result = diagnose("UI 起不来", SETTINGS, client=client)
        assert not result.deterministic
        assert "端口被占用" in result.reply
        assert len(result.steps) == 2
        assert any("port 7860" in o for o in client.tool_outputs)


class TestCli:
    def test_doctor_checkup_no_args(self, monkeypatch):
        for var in ("API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
        monkeypatch.setattr("seatunnel_agent.settings_store.apply_to_env",
                            lambda: None)
        r = CliRunner().invoke(cli, ["doctor"])
        assert r.exit_code == 0, r.output
        assert "环境体检" in r.output

    def test_doctor_with_fake_llm(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "sk-test")

        def fake_client(settings, tools=None, agent=None, **kw):
            return ScriptedClient([_text("诊断:一切正常")])
        monkeypatch.setattr("seatunnel_agent.llm.LLMClient", fake_client)
        r = CliRunner().invoke(cli, ["doctor", "LLM 超时"])
        assert r.exit_code == 0, r.output
        assert "一切正常" in r.output


class TestLogTailSafety:
    def test_sensitive_filename_refused(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("API_KEY=sk-real-secret", encoding="utf-8")
        out = read_log_tail(str(f))
        assert "refused" in out and "sk-real-secret" not in out
        for name in ("credentials.txt", "id_rsa", "llm_settings.json"):
            (tmp_path / name).write_text("x", encoding="utf-8")
            assert "refused" in read_log_tail(str(tmp_path / name)), name

    def test_secrets_in_ordinary_log_masked(self, tmp_path):
        f = tmp_path / "app.log"
        f.write_text('connecting with password = "hunter2-prod"\n'
                     "ak = AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")
        out = read_log_tail(str(f))
        assert "hunter2-prod" not in out
        assert "AKIAIOSFODNN7EXAMPLE" not in out
        assert "masked" in out
