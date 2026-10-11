# -*- coding: utf-8 -*-
"""Platform plugin manifest — see seatunnel_agent.registry."""

from ..registry import AgentManifest

MANIFEST = AgentManifest(
    name="llm_cost",
    workspace="ai",
    route="/llmcost",
    page_title="LLM Cost",
    logo="$",
    color="#f59e0b",
    title_en="LLM Cost",
    title_zh="LLM 成本观测",
    desc_en=("Cost & usage dashboard over the LLM call log — pricing table, per-model/day charts, anomaly flags"),
    desc_zh=("基于调用日志的成本用量看板 — 价格表、按模型/按天图表、异常标记"),
    render="seatunnel_agent.llm_cost_ui:render_llm_cost_page",
    api="seatunnel_agent.llm_cost.api:router",
    order=40,
)
