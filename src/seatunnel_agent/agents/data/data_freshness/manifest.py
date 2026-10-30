"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="data_freshness",
    workspace="data",
    route="/freshness",
    page_title="Data Freshness",
    logo="FR",
    color="#b45309",
    title_en="Data Freshness Monitor",
    title_zh="数据新鲜度监控",
    desc_en="Update-event inventory to per-table verdicts — which outputs "
            "are late, stalled or stale, judged against rules or the "
            "inferred cadence",
    desc_zh="表更新事件清单 → 按表判定 — 哪些产出迟到、断更、过期，"
            "按规则或推断的节奏评估",
    api="seatunnel_agent.agents.data.data_freshness.api:router",
    group="quality",
    order=56,
    external=True,
    tools=(
        ToolManifest(
            name="data_freshness",
            ref="seatunnel_agent.agents.data.data_freshness.tools:data_freshness",
            desc_zh="数据新鲜度判定（更新事件 JSON/CSV → 迟到/断更/过期报告）",
            desc_en="Data freshness verdicts (update events → late/stalled/stale)",
            router_en="Check whether tables were produced on time: parse "
                      "per-table update events (JSON/CSV), take the cadence "
                      "from rules or infer it from history, and flag late, "
                      "stalled and stale outputs.",
            keywords=("新鲜度", "断更", "过期", "迟到", "freshness", "stale",
                      "stalled", "late", "分区", "partition", "产出"),
        ),
    ),
)
