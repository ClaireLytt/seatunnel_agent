"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="metric_diff",
    workspace="data",
    route="/metricdiff",
    page_title="Metric Diff",
    logo="📏",
    color="#9333ea",
    title_en="Metric Diff",
    title_zh="指标口径一致性",
    desc_en="Same-named metrics defined differently across jobs — why two reports disagree",
    desc_zh="同名指标在不同作业里定义不同 — 「两张报表数对不上」的头号原因",
    render="seatunnel_agent.agents.data.metric_diff.ui:render_metric_diff_page",
    group="governance",
    order=40,
)
