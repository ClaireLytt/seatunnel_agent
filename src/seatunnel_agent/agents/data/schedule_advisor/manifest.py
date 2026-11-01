"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="schedule_advisor",
    workspace="data",
    route="/scheduleadvisor",
    page_title="Schedule Advisor",
    logo="SV",
    color="#0d9488",
    title_en="Schedule Advisor",
    title_zh="调度窗口优化",
    desc_en="Durations x dependencies — earliest timeline, SLA margin, "
            "critical path, slack and the peak-parallelism window",
    desc_zh="时长 × 依赖 — 最早排程时间线、SLA 余量、关键路径、松弛与并行峰值窗口",
    api="seatunnel_agent.agents.data.schedule_advisor.api:router",
    group="build",
    order=81,
    external=True,
    tools=(
        ToolManifest(
            name="schedule_advisor",
            ref="seatunnel_agent.agents.data.schedule_advisor.tools:schedule_advisor",
            desc_zh="调度窗口优化（计划 JSON → 时间线 + 关键路径 + 余量）",
            desc_en="Schedule advice (plan → timeline + critical path)",
            router_en="Advise a scheduling day from a pasted plan (JSON "
                      "with day_start, tasks' durations and "
                      "dependencies, an optional SLA task and deadline): "
                      "the earliest timeline per task, the SLA safety "
                      "margin with thin/negative verdicts, the critical "
                      "path to shorten, per-task slack toward the SLA "
                      "task, the peak-parallelism window and the tasks "
                      "with enough slack to move out of it. No "
                      "scheduler connection.",
            keywords=("调度", "排程", "schedule", "关键路径", "错峰",
                      "sla", "窗口", "依赖", "critical path", "余量"),
        ),
    ),
)
