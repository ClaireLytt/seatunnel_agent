"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="sql_fmt",
    workspace="data",
    route="/sqlfmt",
    page_title="SQL Format",
    logo="🪄",
    color="#4f46e5",
    title_en="SQL Formatter",
    title_zh="SQL 格式化",
    desc_en="Deterministic pretty-print with black-style --check / --write — parse failures kept verbatim",
    desc_zh="确定性排版，black 式 --check / --write — 解析失败原样保留",
    render="seatunnel_agent.agents.data.sql_fmt.ui:render_sql_fmt_page",
    group="quality",
    order=20,
)
