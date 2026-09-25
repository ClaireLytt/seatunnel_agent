"""LLM-driven step execution (``ai:`` steps).

Observe (page digest) -> decide (tool call) -> act -> observe again.
Hard limits: MAX_ROUNDS tool rounds and TOKEN_BUDGET tokens per step —
exceeding either is an ERROR, not a hang.
"""

from __future__ import annotations

import logging
import time

from ..config import load_settings
from ..llm import LLMClient
from .models import Step, StepLog
from .page import DCPage

_log = logging.getLogger(__name__)

MAX_ROUNDS = 8
TOKEN_BUDGET = 30_000

UI_TOOLS = [
    {"name": "click",
     "description": "点击按钮。target 为按钮可见文本(中文或英文均可)。",
     "input_schema": {"type": "object", "properties": {
         "target": {"type": "string"},
         "side": {"type": "string", "enum": ["A", "B"]}},
         "required": ["target"]}},
    {"name": "fill",
     "description": "清空并输入文本框。name 是输入框标签,如 主机/端口/主键列。",
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string"}, "value": {"type": "string"},
         "side": {"type": "string", "enum": ["A", "B"]}},
         "required": ["name", "value"]}},
    {"name": "dropdown",
     "description": ("操作下拉框。先在输入框输入 text 过滤(可为空);"
                     "pick 非空则点击该精确选项完成选择。"),
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string"}, "text": {"type": "string"},
         "pick": {"type": "string"},
         "side": {"type": "string", "enum": ["A", "B"]}},
         "required": ["name"]}},
    {"name": "press",
     "description": "按键,如 Tab / Escape / Enter。in_box 指定先聚焦哪个输入框。",
     "input_schema": {"type": "object", "properties": {
         "keys": {"type": "string"}, "in_box": {"type": "string"},
         "side": {"type": "string", "enum": ["A", "B"]}},
         "required": ["keys"]}},
    {"name": "open_accordion",
     "description": "展开侧边栏手风琴分组,如 校验和/分区比对/质量规则。",
     "input_schema": {"type": "object", "properties": {
         "target": {"type": "string"}}, "required": ["target"]}},
    {"name": "read_page",
     "description": "重新观察页面,返回最新页面摘要。",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "done",
     "description": "步骤结束。success=false 时必须给 reason。",
     "input_schema": {"type": "object", "properties": {
         "success": {"type": "boolean"}, "reason": {"type": "string"}},
         "required": ["success"]}},
]

_SYSTEM = """你是 seatunnel_agent 项目「数据对比」页面的 UI 测试执行器。
你收到一条测试步骤指令和当前页面摘要,通过调用工具在真实浏览器中完成该步骤。

规则:
1. 只做指令要求的事,不多点、不探索、不修复页面问题;
2. 每次最多调用一个工具,先看摘要再行动;不确定元素状态时先 read_page;
3. 元素名一律使用页面摘要中出现的标签文本;
4. 指令完成后立即调用 done(success=true);
5. 连续两次行动后页面无变化,或找不到目标元素,调用
   done(success=false, reason=具体原因),不要硬试;
6. 不要输出任何解释文字,只调用工具。"""


class UITestLLM:
    """Shared LLM handle for a whole run — tracks total token spend."""

    def __init__(self):
        self.client = LLMClient(load_settings(), tools=UI_TOOLS)
        self.tokens_used = 0

    def spend(self, usage: dict) -> int:
        n = (usage.get("input_tokens", 0) or 0) + (usage.get("output_tokens", 0) or 0)
        self.tokens_used += n
        return n


def _ms(t0: float) -> int:
    return int((time.time() - t0) * 1000)


def _exec_tool(name: str, inp: dict, dc: DCPage) -> str:
    """Map a tool call onto DCPage; exceptions come back as text so the
    model can adapt instead of the run crashing."""
    try:
        if name == "click":
            dc.click_button(inp["target"], inp.get("side"))
            out = f"clicked '{inp['target']}'"
        elif name == "fill":
            dc.clear_and_type(inp["name"], str(inp.get("value", "")),
                              inp.get("side"))
            out = f"filled '{inp['name']}'"
        elif name == "dropdown":
            nm, side = inp["name"], inp.get("side")
            text, pick = inp.get("text", ""), inp.get("pick", "")
            if pick:
                dc.dropdown_select(nm, pick, side)
                out = f"selected '{pick}' in '{nm}'"
            else:
                dc.dropdown_type(nm, text, side)
                out = f"typed '{text}' in '{nm}'"
        elif name == "press":
            dc.press_in(inp["keys"], inp.get("in_box"), inp.get("side"))
            out = f"pressed {inp['keys']}"
        elif name == "open_accordion":
            dc.open_accordion(inp["target"])
            out = f"opened '{inp['target']}'"
        elif name == "read_page":
            out = "page re-read"
        else:
            return f"ERROR: unknown tool {name}"
        # act-then-observe: append a fresh digest so the model sees the
        # effect without an extra read_page round-trip
        dc.page.wait_for_timeout(600)
        return f"{out}\n\n当前页面摘要:\n{dc.digest()}"
    except Exception as e:  # noqa: BLE001 — feed the error back to the model
        return f"ERROR: {type(e).__name__}: {str(e)[:400]}"


def run_ai_step(step: Step, dc: DCPage, llm: UITestLLM | None) -> StepLog:
    t0 = time.time()
    if llm is None:
        return StepLog(step.desc, False, 0, "跳过: --no-llm 模式")

    step_tokens = 0
    messages: list[dict] = [{
        "role": "user",
        "content": f"步骤指令:{step.ai}\n\n当前页面摘要:\n{dc.digest()}",
    }]
    for round_no in range(MAX_ROUNDS):
        resp = llm.client.chat(_SYSTEM, messages)
        step_tokens += llm.spend(resp.usage)
        if step_tokens > TOKEN_BUDGET:
            return StepLog(step.desc, False, _ms(t0),
                           f"token 预算超限 ({step_tokens} > {TOKEN_BUDGET})")
        if not resp.wants_tool_use:
            return StepLog(step.desc, False, _ms(t0),
                           f"模型未调用工具: {resp.reply_text[:200]}")

        messages.append(llm.client.append_assistant(resp.raw_content))
        results = []
        for tc in resp.tool_calls:
            if tc.name == "done":
                ok = bool(tc.input.get("success"))
                reason = tc.input.get("reason", "")
                return StepLog(step.desc, ok, _ms(t0),
                               f"{round_no + 1} 轮完成"
                               + (f" — {reason}" if reason else ""))
            out = _exec_tool(tc.name, tc.input or {}, dc)
            results.append({"type": "tool_result", "tool_use_id": tc.id,
                            "content": out[:4000]})
        tr = llm.client.build_tool_result_message(results)
        if isinstance(tr, list):
            messages.extend(tr)
        else:
            messages.append(tr)

    return StepLog(step.desc, False, _ms(t0),
                   f"超过 {MAX_ROUNDS} 轮未完成")
