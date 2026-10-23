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
        legacy=None,
        group="build",
        order=20,
        external=True,
    ),
]
