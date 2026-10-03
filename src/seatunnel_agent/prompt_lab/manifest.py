# -*- coding: utf-8 -*-
"""Platform plugin manifest — see seatunnel_agent.registry."""

from ..registry import AgentManifest

MANIFEST = AgentManifest(
    name="prompt_lab",
    workspace="ai",
    route="/promptlab",
    page_title="Prompt Lab",
    logo="PL",
    color="#16a34a",
    title_en="Prompt Lab",
    title_zh="Prompt 实验室",
    desc_en=("Run one prompt across provider profiles side-by-side — outputs, tokens, latency, diff"),
    desc_zh=("同一 Prompt 多个模型档案并排对比 — 输出、token、耗时与差异"),
    render="seatunnel_agent.prompt_lab_ui:render_prompt_lab_page",
    api="seatunnel_agent.prompt_lab.api:router",
    order=30,
)
