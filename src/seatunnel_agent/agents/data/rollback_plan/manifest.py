"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="rollback_plan",
    workspace="data",
    route="/rollbackplan",
    page_title="Rollback Plan",
    logo="RB",
    color="#8a4a2b",
    title_en="Rollback Plan",
    title_zh="回滚编排",
    desc_en="Bad load x lineage — restore the table, re-run downstream "
            "in topological levels, verify every touched table",
    desc_zh="写坏的表 × 血缘 — 恢复坏表、按拓扑分层重跑下游、逐表验证,附估时",
    api="seatunnel_agent.agents.data.rollback_plan.api:router",
    group="build",
    order=89,
    external=True,
    tools=(
        ToolManifest(
            name="rollback_plan",
            ref="seatunnel_agent.agents.data.rollback_plan.tools:rollback_plan",
            desc_zh="回滚编排（坏表 × 血缘 → 分层恢复步骤 + 验证）",
            desc_en="Rollback plan (bad table x lineage → steps)",
            router_en="Orchestrate the recovery from a bad data load: "
                      "paste the pipeline SQL plus the bad table "
                      "(optionally its partitions, the restore mode "
                      "snapshot/rerun/overwrite and a snapshot table); "
                      "the plan restores the table first, re-runs its "
                      "downstream in topological levels (parallel inside "
                      "a level), verifies every touched table, and "
                      "estimates the critical path when per-table "
                      "durations are given. No scheduler connection.",
            keywords=("回滚", "rollback", "写坏", "恢复", "重跑", "下游",
                      "事故", "restore", "backout", "快照"),
        ),
    ),
)
