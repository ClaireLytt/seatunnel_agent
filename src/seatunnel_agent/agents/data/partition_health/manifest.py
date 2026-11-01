"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="partition_health",
    workspace="data",
    route="/partitionhealth",
    page_title="Partition Health",
    logo="PH",
    color="#4d7c0f",
    title_en="Partition Health",
    title_zh="分区健康体检",
    desc_en="Partition listing — date gaps, empty partitions, size skew "
            "and surging or shrunken latest partitions",
    desc_zh="分区清单 — 日期断档/空分区/大小倾斜/最新分区暴涨缩水,附处方",
    api="seatunnel_agent.agents.data.partition_health.api:router",
    group="quality",
    order=83,
    external=True,
    tools=(
        ToolManifest(
            name="partition_health",
            ref="seatunnel_agent.agents.data.partition_health.tools:partition_health",
            desc_zh="分区健康体检（清单 → 断档/空分区/倾斜/涨缩）",
            desc_en="Partition health (listing → gaps/empty/skew)",
            router_en="Check partition health from a pasted listing "
                      "(CSV or JSON rows: table, partition, size_gb, "
                      "optional rows): per table, date gaps in the "
                      "partition sequence (backfill holes), empty "
                      "partitions, size skew against the table median, "
                      "and a surging or shrunken latest partition — "
                      "each with a prescription. Whether partitions "
                      "arrive on time is the data_freshness agent's "
                      "job. No database connection.",
            keywords=("分区", "partition", "断档", "空分区", "倾斜",
                      "缩水", "暴涨", "体检", "回刷", "缺分区"),
        ),
    ),
)
