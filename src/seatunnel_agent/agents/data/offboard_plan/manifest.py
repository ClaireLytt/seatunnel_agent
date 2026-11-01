"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="offboard_plan",
    workspace="data",
    route="/offboardplan",
    page_title="Offboarding Plan",
    logo="OB",
    color="#431407",
    title_en="Offboarding Plan",
    title_zh="下线方案",
    desc_en="A table to retire plus its lineage — downstream blockers "
            "named, then announce / freeze / archive staged, with the "
            "DROP commented until the archive verifies",
    desc_zh="要下线的表 × 血缘 — 下游阻塞点名先迁移,公示/冻结/归档分"
            "阶段编排,DROP 在归档核验前保持注释",
    api="seatunnel_agent.agents.data.offboard_plan.api:router",
    group="governance",
    order=103,
    external=True,
    tools=(
        ToolManifest(
            name="offboard_plan",
            ref="seatunnel_agent.agents.data.offboard_plan.tools:offboard_plan",
            desc_zh="表下线方案（血缘 × 表 → 四阶段下线步骤）",
            desc_en="Offboarding plan (lineage x table → staged steps)",
            router_en="Stage a table retirement nobody gets paged for: "
                      "paste the pipeline SQL and the table, the plan "
                      "walks the lineage downstream — live consumers "
                      "block the plan and are named for migration — "
                      "then stages announce (deadline), freeze (mark "
                      "deprecated, pause the producer; reads keep "
                      "working), archive (snapshot plus a row-count "
                      "verify), and a DROP that stays commented until "
                      "the archive verifies. field_usage finds the "
                      "candidates; this ships the plan. No scheduler or "
                      "database connection.",
            keywords=("下线", "退役", "offboard", "retire", "归档",
                      "drop", "血缘", "下游", "冻结", "治理"),
        ),
    ),
)
