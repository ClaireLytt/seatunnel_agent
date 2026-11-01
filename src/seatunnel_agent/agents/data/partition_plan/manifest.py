"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="partition_plan",
    workspace="data",
    route="/partitionplan",
    page_title="Partition Plan",
    logo="PP",
    color="#1e3a2f",
    title_en="Partition Plan",
    title_zh="分区键选型",
    desc_en="A data sample and the query workload — partition-key "
            "candidates ranked by filter share, time shape and "
            "cardinality band, with the DDL clause ready",
    desc_zh="数据样例 + 查询负载 — 候选分区键按过滤频率/时间形/基数甜区"
            "排名,DDL 子句现成",
    api="seatunnel_agent.agents.data.partition_plan.api:router",
    group="build",
    order=108,
    external=True,
    tools=(
        ToolManifest(
            name="partition_plan",
            ref="seatunnel_agent.agents.data.partition_plan.tools:"
                "partition_plan",
            desc_zh="分区键选型（样例 + 负载 → PARTITIONED BY 推荐）",
            desc_en="Partition-key selection (sample + workload → DDL)",
            router_en="Pick the partition key for a table that has none "
                      "yet: paste a data sample plus the query workload "
                      "and every column is scored by WHERE-filter share, "
                      "time shape (the canonical key) and cardinality "
                      "band (one value prunes nothing, an id column "
                      "explodes the metastore); hot high-cardinality id "
                      "columns get a CLUSTERED BY bucketing suggestion "
                      "instead. partition_health examines partitions a "
                      "table already has; this selects the key for one "
                      "that has none. No database connection.",
            keywords=("分区键", "选型", "partitioned by", "分桶",
                      "clustered by", "裁剪", "建表", "key", "bucket",
                      "新表"),
        ),
    ),
)
