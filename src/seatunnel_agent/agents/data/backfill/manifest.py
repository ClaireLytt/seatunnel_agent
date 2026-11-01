"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="backfill",
    workspace="data",
    route="/backfill",
    page_title="Backfill Plan",
    logo="BF",
    color="#166534",
    title_en="Backfill Planner",
    title_zh="分区补数计划",
    desc_en="Missing partitions x lineage cascade — which tables to re-run, "
            "for which dates, in which order",
    desc_zh="缺失分区 × 血缘级联 — 该补哪些表、哪些日期、按什么顺序跑",
    api="seatunnel_agent.agents.data.backfill.api:router",
    group="quality",
    order=57,
    external=True,
    tools=(
        ToolManifest(
            name="backfill_plan",
            ref="seatunnel_agent.agents.data.backfill.tools:backfill_plan",
            desc_zh="补数计划（更新事件 + 规则 → 缺口、级联重跑与批次顺序）",
            desc_en="Backfill plan (update events + rules → gaps, cascade, batches)",
            router_en="Plan a backfill: find each table's missing partition "
                      "slots from per-table update events (JSON/CSV) and "
                      "cadence rules, cascade the gaps downstream and order "
                      "the impacted tables into topological batches.",
            keywords=("补数", "重跑", "backfill", "rerun", "缺失分区",
                      "missing partition", "级联", "cascade", "断更"),
        ),
    ),
)
