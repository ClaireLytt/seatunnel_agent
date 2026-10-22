"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="sql_testgen",
    workspace="data",
    route="/testgen",
    page_title="Test Data",
    logo="🧪",
    color="#ca8a04",
    title_en="Test Data Generator",
    title_zh="SQL 测试数据生成",
    desc_en="Join-aware datasets that exercise a query, validated on in-memory SQLite",
    desc_zh="关联感知造数，让查询真正跑通 — 内存 SQLite 一键验证",
    api="seatunnel_agent.agents.data.sql_testgen.api:router",
    group="quality",
    order=50,
    external=True,
)
