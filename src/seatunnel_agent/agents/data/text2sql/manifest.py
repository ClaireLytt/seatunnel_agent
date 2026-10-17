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
        render="",  # React static mount serves this route (#67)
        legacy="/text2sql-legacy",
        group="build",
        order=20,
        external=True,
    ),
    AgentManifest(
        name="text2sql_legacy",
        workspace="data",
        route="/text2sql-legacy",
        page_title="Text2SQL Legacy",
        logo="SQL",
        color="#0ea5e9",
        title_en="Text2SQL (legacy)",
        title_zh="Text2SQL(旧版)",
        desc_en="Legacy Gradio page kept until the React migration completes",
        desc_zh="旧版 Gradio 页面,React 迁移完成前保留",
        render="seatunnel_agent.agents.data.text2sql.ui:render_text2sql_page",
        card=False,
    ),
]
