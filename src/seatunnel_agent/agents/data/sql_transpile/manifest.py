"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="sql_transpile",
    workspace="data",
    route="/transpile",
    page_title="SQL Transpile",
    logo="🔁",
    color="#16a34a",
    title_en="SQL Dialect Translation",
    title_zh="SQL 方言翻译",
    desc_en="hive / spark / doris / starrocks translation with an incompatibility report — deterministic, no DB connection",
    desc_zh="hive / spark / doris / starrocks 互转 + 不兼容点清单 — 确定性翻译，不连接数据库",
    render="seatunnel_agent.agents.data.sql_transpile.ui:render_sql_transpile_page",
    group="quality",
    order=30,
)
