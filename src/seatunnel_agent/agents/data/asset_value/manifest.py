"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="asset_value",
    workspace="data",
    route="/assetvalue",
    page_title="Asset Value",
    logo="AV",
    color="#a05c1c",
    title_en="Asset Value",
    title_zh="资产价值评估",
    desc_en="Inventory rows — transparent scoring by access, dependencies "
            "and recency; tiers plus a value x cost quadrant",
    desc_zh="资产清单 — 按访问/依赖/新近度透明打分,分层核心至闲置并给价值×成本象限",
    api="seatunnel_agent.agents.data.asset_value.api:router",
    group="governance",
    order=71,
    external=True,
    tools=(
        ToolManifest(
            name="asset_value",
            ref="seatunnel_agent.agents.data.asset_value.tools:asset_value",
            desc_zh="资产价值评估（清单 → 分层 + 价值×成本象限）",
            desc_en="Asset value grading (inventory → tiers + quadrants)",
            router_en="Grade data assets from an inventory listing (CSV "
                      "or JSON rows: table, size_gb, access_cnt_30d, "
                      "last_access, downstream_cnt): transparent scoring "
                      "— up to 50 pts for 30-day access (log-scaled), 30 "
                      "for downstream dependencies, 20 for recency — "
                      "tiers core/common/edge/idle at 60/35/15, and a "
                      "value x cost quadrant against the median size so "
                      "big-but-idle and small-but-core tables pop out.",
            keywords=("资产", "价值", "评估", "value", "核心", "闲置",
                      "分层", "tier", "治理", "grading", "访问频率"),
        ),
    ),
)
