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

# Vision support is probed once per process: the first failed image call
# disables screenshots for the rest of the run (text-only fallback).
_vision_state: dict = {"ok": None}        # None=untried, True/False=known


def _vision_enabled() -> bool:
    import os
    if os.getenv("UITEST_JUDGE_VISION", "1").lower() in ("0", "false", "no"):
        return False
    return _vision_state["ok"] is not False


def _image_content(provider: str, b64: str, prompt: str) -> list:
    if provider == "anthropic":
        return [
            {"type": "image", "source": {"type": "base64",
                                         "media_type": "image/png",
                                         "data": b64}},
            {"type": "text", "text": prompt},
        ]
    return [
        {"type": "image_url",
         "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": prompt},
    ]


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


# (expectation, digest-hash) -> (ok, reason). In-process only: --repeat N
# re-judges the same expectation against an identical page summary every
# round — that's pure token burn. Screenshots are ignored in the key (they
# differ per capture); an identical text digest is the stability signal.
_judge_cache: dict[tuple[str, str], tuple[bool, str]] = {}


def run_judge(a: Assertion, dc: DCPage, llm: UITestLLM | None) -> StepLog:
    import hashlib

    t0 = time.time()
    expect = str(a.args.get("expect", a.args.get("target", "")))
    if llm is None:
        return StepLog(f"ai_judge: {expect}", False, 0, "跳过: --no-llm 模式")

    digest = dc.digest(max_result_chars=2500)
    cache_key = (expect, hashlib.sha256(digest.encode("utf-8")).hexdigest())
    hit = _judge_cache.get(cache_key)
    if hit is not None:
        ok, reason = hit
        return StepLog(f"ai_judge: {expect}", ok, _ms(t0),
                       f"{reason} (cached)")

    prompt = f"预期:{expect}\n\n当前页面摘要:\n{digest}"

    def _messages(with_image: bool) -> list:
        if with_image:
            try:
                import base64
                b64 = base64.b64encode(dc.page.screenshot()).decode()
                return [{"role": "user", "content": _image_content(
                    llm.client.provider, b64, prompt)}]
            except Exception:  # noqa: BLE001 — screenshot failure -> text only
                pass
        return [{"role": "user", "content": prompt}]

    obj = None
    use_image = _vision_enabled()
    for _ in range(2):                       # one retry on unparseable output
        try:
            resp = llm.client.chat(_SYSTEM, _messages(use_image))
        except Exception:  # noqa: BLE001 — likely a vision-unsupported model
            if not use_image:
                raise
            _vision_state["ok"] = False      # remember for the whole run
            use_image = False
            resp = llm.client.chat(_SYSTEM, _messages(False))
        else:
            if use_image:
                _vision_state["ok"] = True
        llm.spend(resp.usage)
        obj = _parse(resp.reply_text)
        if obj is not None:
            break

    if obj is None:
        return StepLog(f"ai_judge: {expect}", False, _ms(t0),
                       "judge 输出无法解析为 JSON")
    ok = obj["verdict"] == "pass"
    reason = str(obj.get("reason", ""))[:500]
    _judge_cache[cache_key] = (ok, reason)
    return StepLog(f"ai_judge: {expect}", ok, _ms(t0), reason)
