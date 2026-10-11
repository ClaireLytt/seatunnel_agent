# -*- coding: utf-8 -*-
"""Platform plugin manifest — see seatunnel_agent.registry."""

from ..registry import AgentManifest

MANIFEST = AgentManifest(
    name="web_task",
    workspace="ai",
    route="/webtask",
    page_title="Web Task Agent",
    logo="🖱️",
    color="#f97316",
    title_en="Web Task Agent",
    title_zh="网页操作 Agent",
    desc_en=("Goal + URL → a real browser loop: snapshot, click, fill, "
             "observe — confined to the start origin by default"),
    desc_zh=("给目标和 URL → 真实浏览器循环:快照、点击、填表、再观察 — "
             "默认只允许同源页面"),
    render="seatunnel_agent.web_task_ui:render_web_task_page",
    api=None,  # drives a local browser — CLI/UI only
    order=80,
)
