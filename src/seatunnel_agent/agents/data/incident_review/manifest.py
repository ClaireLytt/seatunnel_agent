"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="incident_review",
    workspace="data",
    route="/incidentreview",
    page_title="Incident Review",
    logo="IR",
    color="#450a0a",
    title_en="Incident Review",
    title_zh="事故复盘",
    desc_en="An incident's event log — the timeline plus MTTD/MTTA/MTTR "
            "computed instead of guessed, silent windows named",
    desc_zh="事故事件日志 — 时间线 + 发现/响应/恢复用时按记录计算而非"
            "回忆,静默窗口点名",
    api="seatunnel_agent.agents.data.incident_review.api:router",
    group="build",
    order=109,
    external=True,
    tools=(
        ToolManifest(
            name="incident_review",
            ref="seatunnel_agent.agents.data.incident_review.tools:"
                "incident_review",
            desc_zh="事故复盘（事件日志 → 时间线与用时指标）",
            desc_en="Incident review (event log → timeline + durations)",
            router_en="Compute a postmortem's numbers instead of "
                      "guessing them: paste the incident's event log "
                      "(time, kind: impact/alert/action/comm/recovery, "
                      "text) and get the normalized timeline plus MTTD "
                      "(impact to first alert), MTTA (alert to first "
                      "action) and MTTR (impact to last recovery), with "
                      "detection lag, response lag, mid-incident silent "
                      "windows and a missing recovery event graded. "
                      "task_failure explains why a job crashed; this "
                      "reviews how the incident was handled. No "
                      "monitoring connection.",
            keywords=("复盘", "postmortem", "mttr", "incident", "时间线",
                      "事故", "mttd", "响应", "恢复", "值班"),
        ),
    ),
)
