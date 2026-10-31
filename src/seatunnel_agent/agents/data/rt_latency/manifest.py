"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="rt_latency",
    workspace="data",
    route="/rtlatency",
    page_title="RT Latency",
    logo="RL",
    color="#4d7c0f",
    title_en="RT Latency",
    title_zh="实时延迟分析",
    desc_en="Event timestamps — per-hop and end-to-end p50/p95/max, the "
            "dominant hop, outlier events and SLA breaches",
    desc_zh="事件时间戳 — 分段与端到端 p50/p95/max、主导段、离群事件与 SLA 破线数",
    api="seatunnel_agent.agents.data.rt_latency.api:router",
    group="quality",
    order=77,
    external=True,
    tools=(
        ToolManifest(
            name="rt_latency",
            ref="seatunnel_agent.agents.data.rt_latency.tools:rt_latency",
            desc_zh="实时延迟分析（事件时间戳 → 分段分位 + 离群事件）",
            desc_en="RT latency (event timestamps → hop percentiles)",
            router_en="Trace end-to-end latency from pasted event "
                      "timestamp rows (CSV or JSONL: event_id plus the "
                      "*_ts stage columns such as produce/ingest/"
                      "process/sink, ISO or epoch-ms): per-hop and "
                      "end-to-end p50/p95/max, the dominant hop where "
                      "p95 time goes, outlier events above 3x the median with "
                      "their worst hop, and SLA breach counts against an "
                      "optional threshold.",
            keywords=("延迟", "latency", "端到端", "实时", "p95",
                      "时效", "lag", "事件", "链路", "慢在哪"),
        ),
    ),
)
