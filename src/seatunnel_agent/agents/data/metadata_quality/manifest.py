"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="metadata_quality",
    workspace="data",
    route="/metaquality",
    page_title="Metadata Quality",
    logo="📐",
    color="#b45309",
    title_en="Metadata Quality",
    title_zh="元数据质量体检",
    desc_en="DDL conventions: comment coverage, cross-layer naming, type anti-patterns",
    desc_zh="DDL 规约 — 注释覆盖率、跨层命名错配、类型反模式",
    api="seatunnel_agent.agents.data.metadata_quality.api:router",
    group="governance",
    order=52,
    external=True,
)
