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
    # api intentionally unset: the router is mounted unconditionally by the
    # launcher (the React page depends on it), not behind --api.
    render="seatunnel_agent.agents.data.sql_review.ui:render_sql_review_page",
    group="quality",
    order=10,
)
