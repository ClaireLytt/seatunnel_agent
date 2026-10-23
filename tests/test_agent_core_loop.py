"""Loop-level tests for the deepened ToolLoopAgent seams (ticket loop-01):
events, stop signal, per-turn hint, truncation policy — all driven through
the injectable scripted client, offline."""
from __future__ import annotations

import threading

from seatunnel_agent.agent_core import ToolLoopAgent, ToolSpec
from seatunnel_agent.common.config import Settings
from seatunnel_agent.common.llm import LLMResponse, ToolCall
from tests.conftest import llm_text, llm_tool

SETTINGS = Settings(api_key="sk-test")

ECHO = ToolSpec(name="echo", description="echo",
                input_schema={"type": "object"},
                run=lambda **kw: f"echo:{kw}")


class ScriptedClient:
    """Shared-loop test double; records chat kwargs and can stream deltas."""

    def __init__(self, responses, deltas=None):
        self.responses = list(responses)
        self.deltas = list(deltas or [])
        self.systems: list[str] = []
        self.saw_delta_cb: list[bool] = []

    def chat(self, system, messages, on_text_delta=None):
        self.systems.append(system)
        self.saw_delta_cb.append(on_text_delta is not None)
        if on_text_delta:
            for chunk in self.deltas:
                on_text_delta(chunk)
        return self.responses.pop(0) if self.responses else llm_text("done")

    def append_assistant(self, raw):
        return {"role": "assistant", "content": [raw]}

    def build_tool_result_message(self, results):
        return {"role": "user", "content": results}


def _agent(responses, **kw):
    client = ScriptedClient(responses)
    return ToolLoopAgent(SETTINGS, [ECHO], "sys", "t",
                         client=client, **kw), client


def test_defaults_unchanged_no_delta_callback_passed():
    agent, client = _agent([llm_text("hi")])
    out = agent.run("q")
    assert out.reply == "hi" and not out.stopped
    assert client.saw_delta_cb == [False]  # no on_event → plain chat call


def test_result_to_dict_contains_stopped_flag():
    agent, _ = _agent([llm_text("hi")])
    assert agent.run("q").to_dict()["stopped"] is False


def test_on_event_step_usage_and_text_delta():
    events: list[tuple[str, dict]] = []
    client = ScriptedClient(
        [llm_tool("echo", {"a": 1}, usage={"input_tokens": 5}),
         llm_text("done", usage={"output_tokens": 7})],
        deltas=["he", "llo"])
    agent = ToolLoopAgent(SETTINGS, [ECHO], "sys", "t", client=client,
                          on_event=lambda t, d: events.append((t, d)))
    out = agent.run("q")
    assert out.reply == "done"
    kinds = [t for t, _ in events]
    assert kinds.count("step") == 1
    assert kinds.count("usage") == 2
    assert [d["text"] for t, d in events if t == "text_delta"] == \
        ["he", "llo", "he", "llo"]
    step_payloads = [d for t, d in events if t == "step"]
    assert step_payloads[0]["tool"] == "echo"


def test_stop_before_first_turn():
    stop = threading.Event()
    stop.set()
    agent, client = _agent([llm_text("never")], stop_event=stop)
    out = agent.run("q")
    assert out.stopped and out.reply == "stopped by user"
    assert client.systems == []  # no LLM call at all


def test_stop_between_tool_calls_answers_dangling_tool_use():
    stop = threading.Event()

    def stopping_run(**kw):
        stop.set()
        return "first ran"

    first = ToolSpec(name="first", description="", input_schema={},
                     run=stopping_run)
    resp = LLMResponse(wants_tool_use=True, tool_calls=[
        ToolCall(id="t1", name="first", input={}),
        ToolCall(id="t2", name="echo", input={}),
    ], thinking_text="", reply_text="", raw_content={"f": 1}, usage={})
    client = ScriptedClient([resp])
    agent = ToolLoopAgent(SETTINGS, [first, ECHO], "sys", "t",
                          client=client, stop_event=stop)
    out = agent.run("q")
    assert out.stopped
    assert [s.tool for s in out.steps] == ["first"]  # second never executed
    # the dangling tool_use got a cancelled tool_result
    results = agent.messages[-1]["content"]
    assert any(r["tool_use_id"] == "t2" and "cancelled" in r["content"]
               for r in results)


def test_system_hint_appended_per_turn():
    hints = iter([" HINT1", " HINT2"])
    agent, client = _agent(
        [llm_tool("echo", {}), llm_text("done")],
        system_hint=lambda: next(hints))
    agent.run("q")
    assert client.systems == ["sys HINT1", "sys HINT2"]


def test_truncate_policy_applied_before_each_call():
    calls: list[int] = []

    def policy(messages):
        calls.append(len(messages))
        return messages[-3:]

    agent, _ = _agent([llm_tool("echo", {}), llm_text("done")],
                      truncate=policy)
    agent.run("q")
    assert len(calls) == 2
    assert len(agent.messages) <= 5  # policy kept history bounded


def test_forced_summary_repairs_dangling_tool_use():
    responses = [llm_tool("echo", {}, cid=f"c{i}") for i in range(3)]
    responses.append(llm_tool("echo", {}, cid="last"))  # summary turn misbehaves
    client = ScriptedClient(responses)
    agent = ToolLoopAgent(SETTINGS, [ECHO], "sys", "t",
                          client=client, max_steps=3)
    out = agent.run("q")
    assert out.truncated
    assert out.reply == "step limit reached"
    results = agent.messages[-1]["content"]
    assert any(r["tool_use_id"] == "last" for r in results)


def test_turn_and_tool_call_events():
    events: list[tuple[str, dict]] = []
    client = ScriptedClient([llm_tool("echo", {"a": 1}), llm_text("done")])
    agent = ToolLoopAgent(SETTINGS, [ECHO], "sys", "t", client=client,
                          on_event=lambda t, d: events.append((t, d)))
    agent.run("q")
    kinds = [t for t, _ in events]
    # tool_call fires BEFORE its step
    assert kinds.index("tool_call") < kinds.index("step")
    assert [d for t, d in events if t == "tool_call"] == \
        [{"name": "echo", "input": {"a": 1}}]
    turns = [d for t, d in events if t == "turn"]
    assert turns[-1]["text"] == "done"


def test_on_limit_policy_replaces_forced_summary():
    responses = [llm_tool("echo", {}, cid=f"c{i}") for i in range(2)]
    client = ScriptedClient(responses)
    agent = ToolLoopAgent(SETTINGS, [ECHO], "sys", "t", client=client,
                          max_steps=2, on_limit=lambda: "fallback report")
    out = agent.run("q")
    assert out.truncated and out.reply == "fallback report"
    assert len(client.systems) == 2  # no extra summary LLM call
