"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="sla_trace",
    workspace="data",
    route="/slatrace",
    page_title="SLA Trace",
    logo="ST",
    color="#0f766e",
    title_en="Scheduling Delay Trace",
    title_zh="调度依赖延迟分析",
    desc_en="Task-instance export to critical path — which upstream made the "
            "output late, and by how much",
    desc_zh="任务实例导出 → 关键路径 — 是哪个上游拖慢了产出、各拖了多久",
    api="seatunnel_agent.agents.data.sla_trace.api:router",
    group="build",
    order=26,
    external=True,
    tools=(
        ToolManifest(
            name="sla_trace",
            ref="seatunnel_agent.agents.data.sla_trace.tools:sla_trace",
            desc_zh="调度延迟归因（任务实例 JSON/CSV → 关键路径 + SLA 破线）",
            desc_en="Scheduling delay attribution (task instances → critical path + SLA)",
            router_en="Trace why a scheduled pipeline finished late: parse "
                      "task-instance exports (JSON/CSV), compute the "
                      "critical path to the target task and attribute "
                      "wait vs run time per upstream.",
            keywords=("延迟", "调度", "sla", "关键路径", "critical path",
                      "late", "airflow", "dolphinscheduler", "超时"),
        ),
    ),
)
