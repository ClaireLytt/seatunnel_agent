"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="layer_check",
    workspace="data",
    route="/layercheck",
    page_title="Layer Check",
    logo="LC",
    color="#0f766e",
    title_en="Layer Check",
    title_zh="数仓分层体检",
    desc_en="SQL lineage x layer topology — layer skips, reverse "
            "dependencies, same-layer chaining and unknown layers",
    desc_zh="SQL 血缘 × 分层拓扑 — 跨层引用/反向依赖/同层叠加/未知分层,附整改处方",
    api="seatunnel_agent.agents.data.layer_check.api:router",
    group="governance",
    order=82,
    external=True,
    tools=(
        ToolManifest(
            name="layer_check",
            ref="seatunnel_agent.agents.data.layer_check.tools:layer_check",
            desc_zh="数仓分层体检（SQL 血缘 → 分层违规 + 处方）",
            desc_en="Layering check (SQL lineage → violations)",
            router_en="Check warehouse layering conformance from pasted "
                      "pipeline SQL: tables get layers from their name "
                      "prefixes (ods/stg, dwd/dim, dws/dwm, ads/rpt/app, "
                      "or a custom prefix-rank map) and every lineage "
                      "edge is judged — layer skips (ods read straight "
                      "into dws/ads), reverse dependencies (a lower "
                      "layer reading a higher one), same-layer chaining "
                      "in the aggregate layers, and unknown-layer "
                      "names — each with a refactoring prescription. No "
                      "database connection.",
            keywords=("分层", "数仓", "layer", "规范", "跨层", "反向依赖",
                      "ods", "dwd", "dws", "ads", "建模", "体检"),
        ),
    ),
)
