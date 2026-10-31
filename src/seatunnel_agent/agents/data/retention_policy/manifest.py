"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="retention_policy",
    workspace="data",
    route="/retention",
    page_title="Retention Advice",
    logo="RT",
    color="#134e4a",
    title_en="Retention Advice",
    title_zh="生命周期建议",
    desc_en="A partition inventory in, per-table TTLs out — archive and "
            "purge candidates with the gigabytes they free, reproducible "
            "from the data's own dates",
    desc_zh="分区清单进,逐表 TTL 出 — 可归档/可清理分区与释放空间,基准"
            "日取数据自身,同清单必得同建议",
    api="seatunnel_agent.agents.data.retention_policy.api:router",
    group="governance",
    order=104,
    external=True,
    tools=(
        ToolManifest(
            name="retention_policy",
            ref="seatunnel_agent.agents.data.retention_policy.tools:"
                "retention_policy",
            desc_zh="生命周期建议（分区清单 → TTL/归档/清理）",
            desc_en="Retention advice (partition inventory → TTLs)",
            router_en="Advise table retention from a partition "
                      "inventory (table, partition, size_gb, "
                      "last_access): the suggested TTL is the age of "
                      "the oldest partition anyone still reads plus a "
                      "grace, archive candidates are past-TTL unread "
                      "partitions with the gigabytes they free, purge "
                      "candidates were never read at all. storage_cost "
                      "prices what is held; this decides what to keep. "
                      "No database connection.",
            keywords=("ttl", "生命周期", "保留", "retention", "归档",
                      "清理", "分区", "过期", "释放", "存储"),
        ),
    ),
)
