"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="data_skew",
    workspace="data",
    route="/dataskew",
    page_title="Data Skew",
    logo="⚖",
    color="#f59e0b",
    title_en="Data Skew Analyzer",
    title_zh="数据倾斜分析",
    desc_en="Detect SQL data-skew patterns statically and rewrite with LLM — Spark SQL / MaxCompute SQL",
    desc_zh="静态识别 SQL 数据倾斜写法并用 LLM 改写优化 —— 支持 Spark SQL / MaxCompute SQL",
    api="seatunnel_agent.agents.data.data_skew.api:router",
    render="",  # React static mount serves this route (frontend/data_skew)
    group="quality",
    order=40,
    external=True,
)
