"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="lineage_hygiene",
    workspace="data",
    route="/hygiene",
    page_title="Warehouse Hygiene",
    logo="🧹",
    color="#0d9488",
    title_en="Warehouse Hygiene",
    title_zh="数仓卫生检查",
    desc_en="Lineage-driven dead weight: write-only tables, dead columns, dangling DDL",
    desc_zh="血缘驱动的死重报告 — 只写不读的表、无人取的列、悬空 DDL",
    api="seatunnel_agent.agents.data.lineage_hygiene.api:router",
    group="governance",
    order=51,
    external=True,
)
