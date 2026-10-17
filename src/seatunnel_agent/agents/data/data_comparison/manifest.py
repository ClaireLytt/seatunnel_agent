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
    # api intentionally unset: the router is mounted unconditionally by the
    # launcher (the React page depends on it), not behind --api.
    render="",  # React static mount serves this route (frontend/datacompare)
    group="build",
    order=30,
    external=True,
)
