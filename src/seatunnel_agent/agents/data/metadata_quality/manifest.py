"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="metadata_quality",
    workspace="data",
    route="/metaquality",
    page_title="Metadata Quality",
    logo="MQ",
    color="#b45309",
    title_en="Metadata Quality",
    title_zh="元数据质量体检",
    desc_en="DDL conventions: comment coverage, cross-layer naming, type anti-patterns",
    desc_zh="DDL 规约 — 注释覆盖率、跨层命名错配、类型反模式",
    api="seatunnel_agent.agents.data.metadata_quality.api:router",
    group="governance",
    order=52,
    external=True,
    tools=(
        ToolManifest(
            name="metadata_quality",
            ref="seatunnel_agent.agents.data.metadata_quality.tools:metadata_quality",
            desc_zh="DDL 规约体检（注释覆盖/分层命名/类型反模式）",
            desc_en="DDL conventions check (comment coverage / layer naming / type anti-patterns)",
            router_en="DDL conventions: comment coverage, cross-layer "
                      "naming mismatches, type anti-patterns.",
            keywords=("注释覆盖", "建表规范", "元数据质量", "命名规范",
                      "comment coverage", "naming convention"),
        ),
    ),
)
