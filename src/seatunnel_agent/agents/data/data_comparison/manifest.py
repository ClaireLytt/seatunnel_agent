"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="data_comparison",
    workspace="data",
    route="/datacompare",
    page_title="Data Comparison",
    logo="⇄",
    color="#8b5cf6",
    title_en="Data Comparison",
    title_zh="数据比对",
    desc_en="Compare schemas, row counts, and data across two data sources",
    desc_zh="跨数据源比对表结构、行数、数据差异",
    render="seatunnel_agent.agents.data.data_comparison.ui:render_data_comparison_page",
    group="build",
    order=30,
)
