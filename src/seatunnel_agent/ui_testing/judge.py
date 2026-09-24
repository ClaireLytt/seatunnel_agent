"""LLM fuzzy-assertion judge.

Single round, no tools, forced-JSON output — a separate call from the
execution agent so the verdict isn't polluted by execution context.
"""

from __future__ import annotations

import json
import re
import time

from .agent import UITestLLM
from .models import Assertion, StepLog
from .page import DCPage

_SYSTEM = """你是 UI 测试断言判定器。给你一条预期描述和当前页面摘要,
判断页面是否满足预期。只输出一个 JSON 对象,不要任何其他文字:
{"verdict": "pass" 或 "fail", "reason": "一句话依据,引用页面中的具体证据"}"""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _ms(t0: float) -> int:
    return int((time.time() - t0) * 1000)


def _parse(text: str) -> dict | None:
    m = _JSON_RE.search(text or "")
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict) or obj.get("verdict") not in ("pass", "fail"):
        return None
    return obj


def run_judge(a: Assertion, dc: DCPage, llm: UITestLLM | None) -> StepLog:
    t0 = time.time()
    expect = str(a.args.get("expect", a.args.get("target", "")))
    if llm is None:
        return StepLog(f"ai_judge: {expect}", False, 0, "跳过: --no-llm 模式")

    prompt = (f"预期:{expect}\n\n当前页面摘要:\n"
              f"{dc.digest(max_result_chars=2500)}")
    messages = [{"role": "user", "content": prompt}]

    obj = None
    for _ in range(2):                       # one retry on unparseable output
        resp = llm.client.chat(_SYSTEM, messages)
        llm.spend(resp.usage)
        obj = _parse(resp.reply_text)
        if obj is not None:
            break

    if obj is None:
        return StepLog(f"ai_judge: {expect}", False, _ms(t0),
                       "judge 输出无法解析为 JSON")
    ok = obj["verdict"] == "pass"
    return StepLog(f"ai_judge: {expect}", ok, _ms(t0),
                   str(obj.get("reason", ""))[:500])
