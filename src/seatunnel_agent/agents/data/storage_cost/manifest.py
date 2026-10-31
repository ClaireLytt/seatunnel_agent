"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="storage_cost",
    workspace="data",
    route="/storagecost",
    page_title="Storage Cost",
    logo="SC",
    color="#166534",
    title_en="Storage Cost",
    title_zh="存储成本治理",
    desc_en="Inventory x partitions — cold-tier moves, expired-partition "
            "drops and small-file compaction with GB estimates",
    desc_zh="清单 × 分区明细 — 迁冷/清理过期分区/小文件合并,每条动作带预计释放 GB",
    api="seatunnel_agent.agents.data.storage_cost.api:router",
    group="governance",
    order=72,
    external=True,
    tools=(
        ToolManifest(
            name="storage_cost",
            ref="seatunnel_agent.agents.data.storage_cost.tools:storage_cost",
            desc_zh="存储成本治理（清单 ± 分区 → 迁冷/清理/合并动作）",
            desc_en="Storage cost (inventory ± partitions → actions)",
            router_en="Turn a storage inventory (CSV/JSON rows with "
                      "size_gb, 30-day access, last access, downstream "
                      "count, optional avg_file_mb) and an optional "
                      "partition listing into ranked governance actions: "
                      "cold-tier moves for big untouched tables, drops "
                      "for date-shaped partitions past the retention "
                      "window, and small-file compaction — each with the "
                      "estimated GB freed or moved.",
            keywords=("存储", "成本", "清理", "storage", "cost", "冷存储",
                      "过期分区", "小文件", "合并", "释放", "治理"),
        ),
    ),
)
