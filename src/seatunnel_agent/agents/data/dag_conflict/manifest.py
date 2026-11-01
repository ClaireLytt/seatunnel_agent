"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="dag_conflict",
    workspace="data",
    route="/dagconflict",
    page_title="DAG Conflict",
    logo="DC",
    color="#c2410c",
    title_en="DAG Conflicts",
    title_zh="并发冲突检测",
    desc_en="Concurrent DAGs on one cluster — over-capacity windows, "
            "write-write conflicts and a verified stagger suggestion",
    desc_zh="多 DAG 同集群并发 — 超容时间窗、写写冲突与验证过的错峰建议",
    api="seatunnel_agent.agents.data.dag_conflict.api:router",
    group="build",
    order=29,
    external=True,
    tools=(
        ToolManifest(
            name="dag_conflict",
            ref="seatunnel_agent.agents.data.dag_conflict.tools:dag_conflict",
            desc_zh="并发冲突检测（多 DAG 场景 → 超容窗/写写冲突/错峰建议）",
            desc_en="DAG conflicts (scenario → windows/write clashes/stagger)",
            router_en="Detect conflicts when several DAGs run concurrently "
                      "on one cluster: ASAP-schedule each DAG from declared "
                      "durations and resources, find the windows where slot "
                      "or memory demand exceeds the capacity, cross-DAG "
                      "write-write conflicts on the same table, and a "
                      "stagger suggestion verified by re-simulation.",
            keywords=("并发", "冲突", "资源争抢", "conflict", "contention",
                      "错峰", "stagger", "同时运行", "超容", "capacity"),
        ),
    ),
)
