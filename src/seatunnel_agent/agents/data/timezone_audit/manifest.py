"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="timezone_audit",
    workspace="data",
    route="/timezoneaudit",
    page_title="Timezone Audit",
    logo="TZ",
    color="#312e81",
    title_en="Timezone Audit",
    title_zh="时间戳体检",
    desc_en="Timestamp columns audited for the four silent corruptions: "
            "mixed offsets, mixed epoch units, the 8-hour bimodal smell, "
            "sentinel years",
    desc_zh="时间戳列四大隐形坏法体检:显式时区不一致/秒毫秒混用/8 小时"
            "双峰嫌疑/哨兵年份",
    api="seatunnel_agent.agents.data.timezone_audit.api:router",
    group="quality",
    order=113,
    external=True,
    tools=(
        ToolManifest(
            name="timezone_audit",
            ref="seatunnel_agent.agents.data.timezone_audit.tools:"
                "timezone_audit",
            desc_zh="时间戳体检（数据行 → 时区/单位/哨兵发现）",
            desc_en="Timezone audit (rows → offset/unit/sentinel findings)",
            router_en="Audit timestamp semantics no type checker sees: "
                      "paste rows and every timestamp-shaped column is "
                      "checked for explicit-offset disagreement in one "
                      "column (direct mixed-zone evidence), epoch "
                      "seconds mixed with milliseconds (aggregates off "
                      "by x1000), an ~8h bimodal hour histogram (the "
                      "UTC-vs-local smell, heuristic), and sentinel "
                      "years outside 1980..2100. dist_anomaly profiles "
                      "numeric distributions; this reads timestamp "
                      "meaning. No database connection.",
            keywords=("时区", "timezone", "时间戳", "utc", "毫秒",
                      "epoch", "双峰", "offset", "哨兵", "混用"),
        ),
    ),
)
