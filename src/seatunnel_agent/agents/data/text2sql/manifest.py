"""Platform plugin manifest — see seatunnel_agent.hub.registry.

One card (/text2sql) plus three card-less auxiliary pages.
"""

from seatunnel_agent.hub.registry import AgentManifest

MANIFESTS = [
    AgentManifest(
        name="text2sql",
        workspace="data",
        route="/text2sql",
        page_title="Text2SQL",
        logo="SQL",
        color="#0ea5e9",
        title_en="Text2SQL · Chat BI",
        title_zh="Text2SQL · Chat BI · 智能问数",
        desc_en="Ask in natural language → auto match table schema → generate & run Hive SQL → preview & CSV export",
        desc_zh="自然语言提问 → 自动匹配表结构 → 生成并执行 Hive SQL → 结果预览与 CSV 导出",
        api="seatunnel_agent.agents.data.text2sql.api:router",
        render="seatunnel_agent.agents.data.text2sql.ui:render_text2sql_page",
        group="build",
        order=20,
    ),
    AgentManifest(
        name="t2s_history",
        workspace="data",
        route="/history",
        page_title="Query History",
        logo="QH",
        color="#0ea5e9",
        title_en="Query History",
        title_zh="查询历史",
        desc_en="Text2SQL run history",
        desc_zh="Text2SQL 查询历史",
        render="seatunnel_agent.agents.data.text2sql.ui:render_history_page",
        card=False,
    ),
    AgentManifest(
        name="t2s_favorites",
        workspace="data",
        route="/favorites",
        page_title="SQL Favorites",
        logo="FV",
        color="#0ea5e9",
        title_en="SQL Favorites",
        title_zh="SQL 收藏",
        desc_en="Saved Text2SQL statements",
        desc_zh="Text2SQL 收藏语句",
        render="seatunnel_agent.agents.data.text2sql.ui:render_favorites_page",
        card=False,
    ),
    AgentManifest(
        name="t2s_schema_browser",
        workspace="data",
        route="/schema-browser",
        page_title="Schema Browser",
        logo="SB",
        color="#0ea5e9",
        title_en="Schema Browser",
        title_zh="表结构浏览",
        desc_en="Browse the Text2SQL schema store",
        desc_zh="浏览 Text2SQL 表结构库",
        render="seatunnel_agent.agents.data.text2sql.ui:render_schema_browser_page",
        card=False,
    ),
]
