"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="sla_board",
    workspace="data",
    route="/slaboard",
    page_title="SLA Board",
    logo="SL",
    color="#78350f",
    title_en="SLA Board",
    title_zh="SLA 达成看板",
    desc_en="Task completion records — per-task attainment, lateness "
            "percentiles and live miss streaks, graded against the "
            "target",
    desc_zh="任务完成记录 — 逐任务达成率/迟到分位/连续破线,对照目标"
            "分级点名,周报一键有数",
    api="seatunnel_agent.agents.data.sla_board.api:router",
    group="build",
    order=100,
    external=True,
    tools=(
        ToolManifest(
            name="sla_board",
            ref="seatunnel_agent.agents.data.sla_board.tools:sla_board",
            desc_zh="SLA 达成看板（完成记录 → 达成率/破线分级）",
            desc_en="SLA board (completion records → graded attainment)",
            router_en="Score data-pipeline SLA attainment from pasted "
                      "completion records (task/date/deadline/finish; "
                      "HH:MM may pass 24 for past-midnight, ISO "
                      "datetimes work too): per-task attainment rate "
                      "vs target, lateness p50/p90/worst, longest and "
                      "live miss streaks — below-target, live-streak "
                      "and chronically-late tasks graded. "
                      "schedule_advisor plans runs, task_failure "
                      "explains crashes; this measures the deadline "
                      "promise. No scheduler connection.",
            keywords=("sla", "达成率", "迟到", "破线", "deadline", "任务",
                      "看板", "attainment", "streak", "按时"),
        ),
    ),
)
