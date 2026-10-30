"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="sync_strategy",
    workspace="data",
    route="/syncstrategy",
    page_title="Sync Strategy",
    logo="SY",
    color="#0f766e",
    title_en="Sync Strategy",
    title_zh="增量同步策略",
    desc_en="Source-table update profile — full, timestamp/PK incremental "
            "or CDC, with reasons and residual risks",
    desc_zh="源表更新特征 — 全量 / 时间戳增量 / 主键增量 / CDC，附理由与风险",
    api="seatunnel_agent.agents.data.sync_strategy.api:router",
    group="build",
    order=28,
    external=True,
    tools=(
        ToolManifest(
            name="sync_strategy",
            ref="seatunnel_agent.agents.data.sync_strategy.tools:sync_strategy",
            desc_zh="增量同步策略推荐（表特征 → 全量/增量/CDC，附理由与风险）",
            desc_en="Sync strategy (table profile → full/incremental/CDC)",
            router_en="Recommend a sync strategy per source table from its "
                      "update characteristics (JSON/CSV inventory or CREATE "
                      "TABLE DDL — row count, churn, update timestamp, "
                      "primary key, deletes, CDC availability, latency): "
                      "full reload, timestamp or PK incremental, or CDC — "
                      "with reasons, residual risks, run cadence, rows-moved "
                      "savings and SeaTunnel config skeletons.",
            keywords=("同步策略", "增量", "全量", "cdc", "binlog",
                      "incremental", "full sync", "sync strategy",
                      "数据同步", "upsert", "ddl", "建表", "调度",
                      "配置骨架"),
        ),
    ),
)
