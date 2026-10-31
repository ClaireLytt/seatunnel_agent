"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="index_advisor",
    workspace="data",
    route="/indexadvisor",
    page_title="Index Advisor",
    logo="IA",
    color="#4d7c0f",
    title_en="Index Advisor",
    title_zh="索引分区推荐",
    desc_en="Query patterns x table DDL — partition, bucketing and "
            "composite-index picks with hit counts",
    desc_zh="查询模式 × 表结构 — 分区、分桶与组合索引推荐，附命中次数",
    api="seatunnel_agent.agents.data.index_advisor.api:router",
    group="governance",
    order=62,
    external=True,
    tools=(
        ToolManifest(
            name="index_advisor",
            ref="seatunnel_agent.agents.data.index_advisor.tools:index_advisor",
            desc_zh="索引分区推荐（查询集合 → 分区/分桶/组合索引与 DDL 片段）",
            desc_en="Index advisor (workload → partition/bucket/index picks)",
            router_en="Recommend indexes, partition and bucketing columns "
                      "from a SQL workload: count per-column equality, "
                      "range, join-key and GROUP BY hits across the "
                      "statements, pick the date-like partition column, "
                      "the hottest join key for bucketing and a composite "
                      "index order, each with hit counts and DDL fragments.",
            keywords=("索引", "分区", "分桶", "index", "partition",
                      "bucket", "clustered by", "建表", "查询模式",
                      "推荐"),
        ),
    ),
)
