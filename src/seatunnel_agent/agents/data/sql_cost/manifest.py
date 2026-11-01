"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="sql_cost",
    workspace="data",
    route="/sqlcost",
    page_title="SQL Cost",
    logo="SC",
    color="#92400e",
    title_en="Cost Estimator",
    title_zh="资源消耗预测",
    desc_en="SQL x table stats — scan, shuffle, memory and wall-clock "
            "estimates with the assumptions stated",
    desc_zh="SQL × 表统计 — 扫描、shuffle、内存与耗时估算，假设全列出",
    api="seatunnel_agent.agents.data.sql_cost.api:router",
    group="quality",
    order=16,
    external=True,
    tools=(
        ToolManifest(
            name="sql_cost",
            ref="seatunnel_agent.agents.data.sql_cost.tools:sql_cost",
            desc_zh="资源消耗预测（SQL + 表统计 → 扫描/shuffle/内存/耗时代价卡）",
            desc_en="Cost estimate (SQL + stats → scan/shuffle/memory/time)",
            router_en="Estimate a SQL statement's resource cost from the "
                      "declared table stats: scan bytes with partition and "
                      "column pruning discounts, join/aggregation shuffle "
                      "bytes, output rows, peak task memory, core-seconds "
                      "and a wall-clock band at a suggested parallelism — "
                      "assumptions listed with the result.",
            keywords=("资源", "消耗", "预估", "cost", "estimate", "内存",
                      "耗时", "扫描量", "shuffle", "多少钱", "多大"),
        ),
    ),
)
