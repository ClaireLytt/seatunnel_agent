"""Platform plugin manifest — see seatunnel_agent.hub.registry.

Two pages share this package: lineage and change-impact.
"""

from seatunnel_agent.hub.registry import AgentManifest

MANIFESTS = [
    AgentManifest(
        name="data_lineage",
        workspace="data",
        route="/lineage",
        page_title="Lineage",
        logo="⇆",
        color="#0891b2",
        title_en="Data Lineage",
        title_zh="数据血缘",
        desc_en="Table & column lineage from SQL files, SeaTunnel configs and Hive metadata — impact, SLA, health",
        desc_zh="从 SQL / SeaTunnel 配置 / Hive 元数据构建表级与字段级血缘 — 影响分析、SLA、治理体检",
        # api intentionally unset: the router is mounted unconditionally by
        # the launcher (the React page depends on it), not behind --api.
        render="",  # React static mount serves this route (frontend/data_lineage)
        group="governance",
        order=10,
        external=True,
    ),
    AgentManifest(
        name="change_impact",
        workspace="data",
        route="/impact",
        page_title="Change Impact",
        logo="Δ",
        color="#e11d48",
        title_en="Change Impact Analysis",
        title_zh="变更影响分析",
        desc_en="SQL diff × lineage — compare two SQL trees and report the release blast radius with severity levels",
        desc_zh="SQL 变更 × 血缘 — 对比两份 SQL 目录，输出上线影响面与严重度分级",
        render="seatunnel_agent.agents.data.data_lineage.ui_impact:render_impact_page",
        group="governance",
        order=20,
    ),
]
