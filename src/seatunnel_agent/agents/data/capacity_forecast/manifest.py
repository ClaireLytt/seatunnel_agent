"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="capacity_forecast",
    workspace="data",
    route="/capacityforecast",
    page_title="Capacity Forecast",
    logo="CF",
    color="#a05c1c",
    title_en="Capacity Forecast",
    title_zh="容量耗尽预测",
    desc_en="Storage series x quota — exhaustion date from recent "
            "slopes, top growers and shrinking metrics",
    desc_zh="存储序列 × 配额 — 按近期斜率外推耗尽日期,增长大户与缩小指标排行",
    api="seatunnel_agent.agents.data.capacity_forecast.api:router",
    group="governance",
    order=84,
    external=True,
    tools=(
        ToolManifest(
            name="capacity_forecast",
            ref="seatunnel_agent.agents.data.capacity_forecast.tools:capacity_forecast",
            desc_zh="容量耗尽预测（序列 × 配额 → 耗尽日期 + 增长大户）",
            desc_en="Capacity forecast (series x quota → exhaustion)",
            router_en="Forecast capacity exhaustion from pasted storage "
                      "series (date,metric,value rows; metric = table, "
                      "value = GB or rows; a metric named total is used "
                      "directly) against a quota: least-squares slopes "
                      "over the recent window, linear extrapolation to "
                      "the exhaustion date with 90/30-day alarms, the "
                      "top growers with their share of the growth, and "
                      "the shrinking metrics. No storage connection.",
            keywords=("容量", "capacity", "耗尽", "quota", "配额",
                      "增长", "存储", "预测", "forecast", "磁盘"),
        ),
    ),
)
