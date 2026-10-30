"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="dag_optimize",
    workspace="data",
    route="/dagopt",
    page_title="DAG Optimize",
    logo="DX",
    color="#9a3412",
    title_en="DAG Optimizer",
    title_zh="DAG 依赖优化",
    desc_en="Redundant serial edges x parallel waves x critical path — "
            "where the schedule wastes time and how to parallelize",
    desc_zh="冗余串行边 × 并行批次 × 关键路径 — 调度在哪儿浪费时间、怎么并行化",
    api="seatunnel_agent.agents.data.dag_optimize.api:router",
    group="governance",
    order=61,
    external=True,
    tools=(
        ToolManifest(
            name="dag_optimize",
            ref="seatunnel_agent.agents.data.dag_optimize.tools:dag_optimize",
            desc_zh="DAG 依赖优化（冗余串行边、并行批次、关键路径与加速比）",
            desc_en="DAG optimization (redundant edges, waves, critical path)",
            router_en="Optimize a task dependency DAG: find unnecessary "
                      "serial dependencies via transitive reduction, layer "
                      "tasks into parallel waves, and compute the "
                      "duration-weighted critical path and ideal speedup.",
            keywords=("依赖优化", "并行", "冗余依赖", "关键路径", "dag",
                      "parallelize", "critical path", "redundant",
                      "transitive reduction", "串行"),
        ),
    ),
)
