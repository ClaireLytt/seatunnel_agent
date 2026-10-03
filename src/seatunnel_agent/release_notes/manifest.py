# -*- coding: utf-8 -*-
"""Platform plugin manifest — see seatunnel_agent.registry."""

from ..registry import AgentManifest

MANIFEST = AgentManifest(
    name="release_notes",
    workspace="devops",
    route="/release",
    page_title="Release Notes",
    logo="🚀",
    color="#ca8a04",
    title_en="Release Notes",
    title_zh="发布助手",
    desc_en=("Grouped changelog from conventional commits + semver bump suggestion; optional LLM polish"),
    desc_zh=("按 conventional commits 分组生成 changelog + 语义化版本建议;可选 LLM 润色"),
    render="seatunnel_agent.release_notes_ui:render_release_notes_page",
    api="seatunnel_agent.release_notes.api:router",
    order=40,
)
