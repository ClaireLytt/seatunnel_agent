"""LLM failure attribution (P1).

On FAIL/ERROR the runner feeds the failure evidence (reason, step logs,
page digest at failure time, app log tail) to a single LLM round and gets a
one-line classification: 前端问题 / 后端异常 / 用例过期 / 环境问题.
"""

from __future__ import annotations

import json
import re

from .agent import UITestLLM
from .models import CaseResult

_SYSTEM = """你是 UI 测试失败归因分析器。根据给出的失败证据,判断失败的最可能原因分类,
只输出一个 JSON 对象:
{"category": "前端问题|后端异常|用例过期|环境问题", "summary": "一句话原因"}

分类标准:
- 前端问题: 页面元素缺失/不可点/渲染错误,但服务端无异常;
- 后端异常: 应用日志出现 Traceback/500,或结果区展示服务端错误;
- 用例过期: 页面行为正常但与断言预期不符(如文案已改、布局调整);
- 环境问题: 端口占用、数据库不可用、超时等基础设施原因。"""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def diagnose(cr: CaseResult, page_digest: str, app_log_tail: str,
             llm: UITestLLM | None) -> str:
    """One-line attribution appended to the case reason.  Empty on any
    problem — diagnosis must never break a run."""
    if llm is None:
        return ""
    try:
        steps = "\n".join(
            f"[{'OK' if s.ok else 'X'}] {s.desc} — {s.detail[:160]}"
            for s in [*cr.steps, *cr.asserts][-8:])
        prompt = (
            f"用例: {cr.case_id} {cr.title}\n"
            f"结论: {cr.verdict} — {cr.reason}\n\n"
            f"最近步骤/断言:\n{steps}\n\n"
            f"失败时页面摘要:\n{page_digest[:2500]}\n\n"
            f"应用日志尾部:\n{app_log_tail[-2000:]}")
        resp = llm.client.chat(_SYSTEM, [{"role": "user", "content": prompt}])
        llm.spend(resp.usage)
        m = _JSON_RE.search(resp.reply_text or "")
        if not m:
            return ""
        obj = json.loads(m.group(0))
        cat, summary = obj.get("category", ""), obj.get("summary", "")
        if not cat:
            return ""
        return f"[归因: {cat}] {summary}"
    except Exception:  # noqa: BLE001
        return ""
