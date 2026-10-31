"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="alert_storm",
    workspace="data",
    route="/alertstorm",
    page_title="Alert Storm",
    logo="AL",
    color="#b33a2e",
    title_en="Alert Storm",
    title_zh="告警风暴聚合",
    desc_en="Alert export clustered by signature — dedup ratio, storm "
            "windows, flapping and noisy sources with suppression hints",
    desc_zh="告警导出按签名聚类 — 降噪倍数、风暴窗口、横跳签名与吵闹来源,附抑制建议",
    api="seatunnel_agent.agents.data.alert_storm.api:router",
    group="build",
    order=86,
    external=True,
    tools=(
        ToolManifest(
            name="alert_storm",
            ref="seatunnel_agent.agents.data.alert_storm.tools:alert_storm",
            desc_zh="告警风暴聚合（导出 → 聚类 + 风暴/横跳/抑制建议）",
            desc_en="Alert storm digest (export → clusters + hints)",
            router_en="Digest an alert-channel export (CSV or JSON rows: "
                      "ts, source, title, level): alerts cluster by a "
                      "normalized title signature so one root cause is "
                      "one row, with the dedup ratio up front; storm "
                      "windows (5-minute bucket over 3x the median), "
                      "flapping signatures (5+ firings inside an hour — "
                      "the suppression candidates) and noisy sources "
                      "each carry a prescription. No alerting-system "
                      "connection.",
            keywords=("告警", "风暴", "alert", "降噪", "聚合", "抑制",
                      "flapping", "storm", "值班", "吵"),
        ),
    ),
)
