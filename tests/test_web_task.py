"""Web-task agent: fake-session loop, origin guard, success heuristic."""

from __future__ import annotations

import pytest

from seatunnel_agent.agents.ai.web_task import run_task
from seatunnel_agent.agents.ai.web_task.session import _origin
from seatunnel_agent.common.config import Settings
from seatunnel_agent.common.llm import LLMResponse, ToolCall

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
        return self.responses.pop(0) if self.responses else _text("DONE: x")

    def append_assistant(self, raw):
        return {"role": "assistant", "content": raw}

    def build_tool_result_message(self, trs):
        self.tool_outputs.extend(t["content"] for t in trs)
        return {"role": "user", "content": trs}


class FakeSession:
    """A one-form page: fill [0], click [1] → submitted state."""

    def __init__(self):
        self.value = ""
        self.submitted = False
        self.closed = False

    def snapshot(self) -> str:
        if self.submitted:
            return "URL: http://x/done\nTITLE: ok\n\n[0] <p> 提交成功"
        return ("URL: http://x/\nTITLE: form\n\n"
                f"[0] <input> placeholder='name' value='{self.value}'\n"
                "[1] <button> Submit")

    def click(self, index: int) -> str:
        if int(index) == 1:
            self.submitted = True
            return "clicked [1]; now at http://x/done"
        return f"clicked [{index}]"

    def fill(self, index: int, text: str) -> str:
        self.value = text
        return f"filled [{index}]"

    def goto(self, url: str) -> str:
        return f"now at {url}"

    def close(self):
        self.closed = True


class TestLoop:
    def test_fill_click_done(self):
        session = FakeSession()
        client = ScriptedClient([
            _tool("snapshot", {}),
            _tool("fill", {"index": 0, "text": "张三"}),
            _tool("click", {"index": 1}),
            _tool("snapshot", {}),
            _text("DONE: 表单已提交,页面显示提交成功。"),
        ])
        result = run_task("提交表单", "http://x/", SETTINGS,
                          session=session, client=client)
        assert result.success
        assert session.submitted and session.value == "张三"
        assert [s.tool for s in result.steps] == [
            "snapshot", "fill", "click", "snapshot"]
        assert "提交成功" in client.tool_outputs[-1]
        assert not session.closed  # injected sessions are the caller's

    def test_failed_reply_not_success(self):
        result = run_task("x", "http://x/", SETTINGS, session=FakeSession(),
                          client=ScriptedClient([_text("FAILED: 页面没有该功能")]))
        assert not result.success

    def test_bad_index_error_isolated(self):
        session = FakeSession()

        def strict_click(index):
            raise ValueError(f"no element [{index}]")
        session.click = strict_click
        client = ScriptedClient([
            _tool("click", {"index": 99}),
            _text("DONE: recovered"),
        ])
        result = run_task("x", "http://x/", SETTINGS, session=session,
                          client=client)
        assert result.steps[0].error
        assert result.success


class TestStartUrlGuard:
    def test_rejects_non_http_schemes(self):
        from seatunnel_agent.agents.ai.web_task.session import validate_start_url
        for url in ("file:///etc/passwd", "ftp://host/x", "javascript:alert(1)",
                    "about:blank", "example.com"):
            with pytest.raises(ValueError):
                validate_start_url(url)

    def test_rejects_literal_private_ips_by_default(self):
        from seatunnel_agent.agents.ai.web_task.session import validate_start_url
        for url in ("http://127.0.0.1:7860/", "https://10.0.0.8/x",
                    "http://192.168.1.1/", "http://169.254.169.254/meta",
                    "http://[::1]/", "http://0.0.0.0/"):
            with pytest.raises(ValueError):
                validate_start_url(url)

    def test_allow_private_and_public_hosts_pass(self, monkeypatch):
        import socket

        from seatunnel_agent.agents.ai.web_task import session as mod

        def fake_gai(host, port, *a, **k):  # hermetic: no real DNS
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "",
                     ("93.184.216.34", 80))]
        monkeypatch.setattr(mod.socket, "getaddrinfo", fake_gai)
        mod.validate_start_url("https://example.com/page")    # public domain
        mod.validate_start_url("http://93.184.216.34/")       # public IP
        mod.validate_start_url("http://127.0.0.1:7860/", allow_private=True)

    def test_hostname_resolving_to_private_ip_is_rejected(self, monkeypatch):
        import socket

        from seatunnel_agent.agents.ai.web_task import session as mod

        def fake_gai(host, port, *a, **k):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "",
                     ("169.254.169.254", 80)),
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "",
                     ("93.184.216.34", 80))]
        monkeypatch.setattr(mod.socket, "getaddrinfo", fake_gai)
        # any private/loopback/link-local resolution rejects the URL
        with pytest.raises(ValueError):
            mod.validate_start_url("http://metadata.internal/latest")
        # allow_private still bypasses the resolution check
        mod.validate_start_url("http://metadata.internal/latest",
                               allow_private=True)

    def test_hostname_resolving_to_public_ip_passes(self, monkeypatch):
        import socket

        from seatunnel_agent.agents.ai.web_task import session as mod

        def fake_gai(host, port, *a, **k):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "",
                     ("93.184.216.34", 80))]
        monkeypatch.setattr(mod.socket, "getaddrinfo", fake_gai)
        mod.validate_start_url("https://example.com/page")

    def test_hostname_resolution_failure_is_allowed(self, monkeypatch):
        import socket

        from seatunnel_agent.agents.ai.web_task import session as mod

        def fake_gai(host, port, *a, **k):
            raise socket.gaierror("NXDOMAIN")
        monkeypatch.setattr(mod.socket, "getaddrinfo", fake_gai)
        # NXDOMAIN/timeout must not reject — the browser will surface the
        # error itself (offline scenarios must not be blocked here)
        mod.validate_start_url("https://no-such-host.example/")

    def test_session_start_validates_before_browser_launch(self):
        from seatunnel_agent.agents.ai.web_task.session import PlaywrightSession
        s = PlaywrightSession()
        with pytest.raises(ValueError):
            s.start("http://127.0.0.1:9/")
        assert s._pw is None  # no Playwright driver was started


class TestOriginGuard:
    def test_origin_parse(self):
        assert _origin("http://127.0.0.1:7860/sqlfmt") == "http://127.0.0.1:7860"
        assert _origin("HTTPS://Example.com/x") == "https://example.com"

    def test_playwright_session_goto_blocked_without_browser(self):
        """The guard fires before any page access — testable browserless."""
        from seatunnel_agent.agents.ai.web_task.session import PlaywrightSession
        s = PlaywrightSession(allow_external=False)
        s.origin = "http://127.0.0.1:7860"
        out = s.goto("https://evil.example.com/")
        assert out.startswith("BLOCKED")


class TestAllowPrivatePassthrough:
    """run_task must forward allow_private to the session it builds
    (the UI's default loopback URL depends on it)."""

    class _Recorder:
        last_kwargs: dict = {}

        def __init__(self, **kwargs):
            TestAllowPrivatePassthrough._Recorder.last_kwargs = kwargs

        def start(self, url):
            raise RuntimeError("stop-here")

        def close(self):
            pass

    def _run(self, monkeypatch, **kw):
        monkeypatch.setattr(
            "seatunnel_agent.agents.ai.web_task.session.PlaywrightSession",
            self._Recorder)
        with pytest.raises(RuntimeError, match="stop-here"):
            run_task("g", "http://127.0.0.1:7860/", SETTINGS,
                     client=ScriptedClient([]), **kw)
        return self._Recorder.last_kwargs

    def test_default_false(self, monkeypatch):
        assert self._run(monkeypatch).get("allow_private") is False

    def test_passthrough_true(self, monkeypatch):
        assert self._run(monkeypatch,
                         allow_private=True).get("allow_private") is True


class TestApi:
    """SSE run endpoint (ticket 01) — OFF unless WEBTASK_API_ENABLED=1."""

    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from seatunnel_agent.agents.ai.web_task.api import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @staticmethod
    def _events(resp):
        import json as _json
        return [_json.loads(line[len("data: "):])
                for line in resp.iter_lines() if line.startswith("data: ")]

    class _FakeFactory:
        """PlaywrightSession stand-in recording kwargs, backed by the
        module-level FakeSession page."""
        last_kwargs: dict = {}

        def __new__(cls, **kwargs):
            TestApi._FakeFactory.last_kwargs = kwargs
            inner = FakeSession()
            inner.start = lambda url: None  # type: ignore[attr-defined]
            return inner

    def test_disabled_403(self, monkeypatch):
        monkeypatch.delenv("WEBTASK_API_ENABLED", raising=False)
        resp = self._client().post("/api/webtask/run",
                                   json={"goal": "g",
                                         "url": "http://127.0.0.1:7860/"})
        assert resp.status_code == 403

    def test_run_streams_steps_then_done(self, monkeypatch):
        monkeypatch.setenv("WEBTASK_API_ENABLED", "1")
        monkeypatch.setenv("API_KEY", "sk-test")
        monkeypatch.setattr(
            "seatunnel_agent.agents.ai.web_task.session.PlaywrightSession",
            self._FakeFactory)
        script = ScriptedClient([
            _tool("fill", {"index": 0, "text": "alice"}),
            _tool("click", {"index": 1}),
            _text("DONE: submitted"),
        ])
        monkeypatch.setattr("seatunnel_agent.common.llm.LLMClient",
                            lambda *a, **k: script)
        with self._client().stream(
                "POST", "/api/webtask/run",
                json={"goal": "submit the form",
                      "url": "http://127.0.0.1:7860/", "lang": "en",
                      "max_steps": 6}) as resp:
            assert resp.status_code == 200
            events = self._events(resp)
        steps = [e for e in events if e["type"] == "step"]
        assert steps and steps[0]["tool"] == "fill"
        done = events[-1]
        assert done["type"] == "done" and done["success"] is True
        # loopback start URL is explicitly permitted over HTTP…
        assert self._FakeFactory.last_kwargs.get("allow_private") is True
        # …while the exposed knobs stay off
        assert self._FakeFactory.last_kwargs.get("allow_external") is False
        assert self._FakeFactory.last_kwargs.get("headed") is False

    def test_non_loopback_private_rejected(self, monkeypatch):
        monkeypatch.setenv("WEBTASK_API_ENABLED", "1")
        monkeypatch.setenv("API_KEY", "sk-test")
        monkeypatch.setattr("seatunnel_agent.common.llm.LLMClient",
                            lambda *a, **k: ScriptedClient([]))
        with self._client().stream(
                "POST", "/api/webtask/run",
                json={"goal": "g", "url": "http://192.168.1.10/",
                      "lang": "en"}) as resp:
            events = self._events(resp)
        assert events[-1]["type"] == "error"
        assert "private" in events[-1]["message"]

    def test_no_key_degrades_to_error_event(self, monkeypatch):
        monkeypatch.setenv("WEBTASK_API_ENABLED", "1")
        for var in ("API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
        monkeypatch.setattr("seatunnel_agent.common.config.load_dotenv",
                            lambda *a, **k: None)
        monkeypatch.setattr(
            "seatunnel_agent.common.settings_store.apply_to_env",
            lambda: None)
        with self._client().stream(
                "POST", "/api/webtask/run",
                json={"goal": "g", "url": "http://127.0.0.1:7860/",
                      "lang": "en"}) as resp:
            events = self._events(resp)
        assert events[-1]["type"] == "error"
        assert "key" in events[-1]["message"].lower() \
            or "LLM" in events[-1]["message"]
