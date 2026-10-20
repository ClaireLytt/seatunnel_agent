"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="sql_review",
    workspace="data",
    route="/sqlreview",
    page_title="SQL Review",
    logo="CR",
    color="#10b981",
    title_en="SQL Code Review",
    title_zh="SQL 代码审查",
    desc_en="Static + LLM review for Hive / Spark / Flink / MaxCompute SQL — performance, quality & standards",
    desc_zh="Hive / Spark / Flink / MaxCompute SQL 静态 + LLM 审查 — 性能、质量与规范",
    api="seatunnel_agent.agents.data.sql_review.api:router",
    render="",  # React static mount serves this route (frontend/sql_review)
    group="quality",
    order=10,
    external=True,
)
