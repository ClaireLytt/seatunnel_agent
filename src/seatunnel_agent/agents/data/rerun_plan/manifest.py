"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="rerun_plan",
    workspace="data",
    route="/rerun",
    page_title="Rerun Plan",
    logo="RR",
    color="#b45309",
    title_en="Rerun Planner",
    title_zh="任务重跑规划",
    desc_en="Failed tasks x downstream closure — the minimal rerun set, "
            "in topological batches, with the blast radius",
    desc_zh="失败节点 × 下游闭包 — 最小重跑集合、拓扑批次与影响面",
    api="seatunnel_agent.agents.data.rerun_plan.api:router",
    group="build",
    order=27,
    external=True,
    tools=(
        ToolManifest(
            name="rerun_plan",
            ref="seatunnel_agent.agents.data.rerun_plan.tools:rerun_plan",
            desc_zh="任务重跑规划（失败节点 + 下游闭包 → 最小重跑批次与影响面）",
            desc_en="Rerun plan (failed nodes + downstream closure → batches)",
            router_en="Plan a minimal-impact rerun after task failures: take "
                      "the failed tasks (named directly or via a scheduler "
                      "status export like {'task':'state'}) and their "
                      "downstream closure as the rerun set, keep upstream "
                      "outputs and sibling branches untouched, and order the "
                      "set into topological batches with the blast radius, "
                      "duration ETA, capacity-limited makespan and "
                      "independent recovery groups.",
            keywords=("重跑", "失败", "rerun", "retry", "failed", "影响面",
                      "blast radius", "下游", "downstream", "恢复",
                      "状态导出", "statuses", "eta", "事故"),
        ),
    ),
)
