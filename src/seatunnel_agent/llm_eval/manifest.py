# -*- coding: utf-8 -*-
"""Platform plugin manifest — see seatunnel_agent.registry."""

from ..registry import AgentManifest

MANIFEST = AgentManifest(
    name="llm_eval",
    workspace="ai",
    route="/llmeval",
    page_title="LLM Eval",
    logo="EV",
    color="#0ea5e9",
    title_en="LLM Eval",
    title_zh="LLM 评测",
    desc_en=("Golden suites for the LLM features — automated scoring, regression gate, score trends"),
    desc_zh=("LLM 功能黄金用例集 — 自动打分、回归门禁、分数趋势"),
    render="seatunnel_agent.llm_eval_ui:render_llm_eval_page",
    api="seatunnel_agent.llm_eval.api:router",
    order=20,
)
