"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="watermark_plan",
    workspace="data",
    route="/watermarkplan",
    page_title="Watermark Plan",
    logo="WM",
    color="#0c4a4e",
    title_en="Watermark Plan",
    title_zh="水位线选型",
    desc_en="Observed events in, a measured watermark bound out — "
            "lateness percentiles, clock skew and stragglers named, "
            "Flink snippets ready",
    desc_zh="观测事件进,实测水位线出 — 迟到分位/时钟漂移/掉队者点名,"
            "Flink 配置片段现成",
    api="seatunnel_agent.agents.data.watermark_plan.api:router",
    group="build",
    order=111,
    external=True,
    tools=(
        ToolManifest(
            name="watermark_plan",
            ref="seatunnel_agent.agents.data.watermark_plan.tools:"
                "watermark_plan",
            desc_zh="水位线选型（事件观测 → 乱序容忍建议）",
            desc_en="Watermark plan (observed events → bound)",
            router_en="Size a Flink job's out-of-orderness bound from "
                      "measurement instead of guessing: paste observed "
                      "events (event_time, arrival_time) and get the "
                      "lateness distribution, the out-of-order share, "
                      "and a suggested bound (regular p99 plus margin; "
                      "hour-plus stragglers are excluded so small "
                      "samples do not degrade p99 to max) with the SQL "
                      "WATERMARK clause and forBoundedOutOfOrderness "
                      "snippet; producer clock skew, heavy tails and "
                      "stragglers graded. rt_latency profiles stage "
                      "latency; this sizes event-time disorder. No "
                      "cluster connection.",
            keywords=("watermark", "水位线", "乱序", "迟到", "flink",
                      "event time", "侧输出", "容忍", "bounded", "选型"),
        ),
    ),
)
