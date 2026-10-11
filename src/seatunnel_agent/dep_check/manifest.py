# -*- coding: utf-8 -*-
"""Platform plugin manifest — see seatunnel_agent.registry."""

from ..registry import AgentManifest

MANIFEST = AgentManifest(
    name="dep_check",
    workspace="devops",
    route="/depcheck",
    page_title="Dependency Health",
    logo="📦",
    color="#0d9488",
    title_en="Dependency Health",
    title_zh="依赖体检",
    desc_en=("Declared vs installed, unpinned specs, duplicate pins and a license inventory — offline"),
    desc_zh=("声明 vs 实装、未钉版本、重复/冲突与 License 清单 — 全离线"),
    render="seatunnel_agent.dep_check_ui:render_dep_check_page",
    api="seatunnel_agent.dep_check.api:router",
    order=30,
)
