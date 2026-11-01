"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="quality_trace",
    workspace="data",
    route="/qualitytrace",
    page_title="Quality Trace",
    logo="QT",
    color="#0f766e",
    title_en="Quality Trace",
    title_zh="质量根因追踪",
    desc_en="Quality event x SQL lineage — upstream suspects scored by "
            "distance and column taint, with verification SQL each",
    desc_zh="质量事件 × SQL 血缘 — 按距离与列级污染给上游打嫌疑分,每个嫌疑附验证 SQL",
    api="seatunnel_agent.agents.data.quality_trace.api:router",
    group="quality",
    order=67,
    external=True,
    tools=(
        ToolManifest(
            name="quality_trace",
            ref="seatunnel_agent.agents.data.quality_trace.tools:quality_trace",
            desc_zh="质量根因追踪（事件 × SQL 血缘 → 嫌疑排行 + 验证 SQL）",
            desc_en="Quality trace (event x lineage → ranked suspects)",
            router_en="Trace a data-quality incident to its upstream "
                      "source: paste the pipeline SQL scripts plus the "
                      "polluted table (optionally the column and a "
                      "one-line symptom), and the ancestors come back "
                      "ranked as suspects — closer tables score higher, "
                      "column-level taint paths add more, transforming "
                      "expressions (SUM/CAST/CASE) are reported as "
                      "mutation points, and each suspect carries a "
                      "copy-ready verification SQL.",
            keywords=("根因", "追踪", "质量", "污染", "trace", "rca",
                      "血缘", "上游", "lineage", "脏数据", "来源"),
        ),
    ),
)
