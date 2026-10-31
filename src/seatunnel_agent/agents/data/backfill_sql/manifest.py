"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="backfill_sql",
    workspace="data",
    route="/backfillsql",
    page_title="Backfill SQL",
    logo="BQ",
    color="#15803d",
    title_en="Backfill SQL",
    title_zh="回溯补数 SQL",
    desc_en="Business dates x partitions — safe, idempotent backfill "
            "statements with pre-flight checks",
    desc_zh="业务日期 × 分区 — 安全幂等的历史补数语句与前置校验",
    api="seatunnel_agent.agents.data.backfill_sql.api:router",
    group="quality",
    order=58,
    external=True,
    tools=(
        ToolManifest(
            name="backfill_sql",
            ref="seatunnel_agent.agents.data.backfill_sql.tools:backfill_sql",
            desc_zh="补数 SQL 生成（业务日期 × 分区 → 幂等补数语句与前置校验）",
            desc_en="Backfill SQL (dates x partitions → idempotent statements)",
            router_en="Generate safe historical backfill SQL: given the "
                      "target table, partition column, business date range "
                      "and a partition-bounded source SELECT, emit one "
                      "idempotent statement block per date (overwrite, "
                      "delete+insert or merge) plus row-count pre-checks.",
            keywords=("补数", "回溯", "backfill", "历史数据", "重刷",
                      "insert overwrite", "分区", "partition", "补历史",
                      "回刷"),
        ),
        ToolManifest(
            name="backfill_specs",
            ref="seatunnel_agent.agents.data.backfill_sql.tools:backfill_specs",
            desc_zh="补数规格桥接（补数计划 JSON → 逐表可编辑的 SQL 规格骨架）",
            desc_en="Backfill spec bridge (planner JSON → per-table specs)",
            router_en="Bridge the backfill planner's plan JSON into one "
                      "ready-to-edit backfill-SQL spec per impacted table, "
                      "carrying the exact missing/cascade dates over.",
            keywords=("补数规格", "spec", "计划转SQL", "plan to sql",
                      "backfill spec"),
        ),
    ),
)
