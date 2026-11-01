"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="field_usage",
    workspace="data",
    route="/fieldusage",
    page_title="Field Usage",
    logo="FU",
    color="#4a2545",
    title_en="Field Usage",
    title_zh="字段使用率",
    desc_en="DDL plus a query workload — per-column reference counts, "
            "never-read tables and columns, SELECT * blind spots, "
            "hottest columns",
    desc_zh="DDL + 查询负载 — 逐列引用计数,没人读的表与列/SELECT * "
            "盲区/最热列 TOP,下线与裁剪的证据链",
    api="seatunnel_agent.agents.data.field_usage.api:router",
    group="governance",
    order=102,
    external=True,
    tools=(
        ToolManifest(
            name="field_usage",
            ref="seatunnel_agent.agents.data.field_usage.tools:field_usage",
            desc_zh="字段使用率盘点（DDL + 查询 → 列级引用计数）",
            desc_en="Field usage (DDL + workload → column ref counts)",
            router_en="Count column-level usage across a query workload: "
                      "paste the CREATE TABLE DDL and a batch of query "
                      "SQL, and every column gets its reference count "
                      "over SELECT/WHERE/JOIN/GROUP BY with per-"
                      "statement alias resolution. Tables the workload "
                      "never reads grade as offboarding candidates, "
                      "never-referenced columns as trimming candidates, "
                      "and SELECT * reads are flagged as blind spots. "
                      "asset_value scores tables; this descends to the "
                      "columns. No database connection.",
            keywords=("字段", "使用率", "列级", "引用", "下线", "裁剪",
                      "usage", "column", "workload", "治理"),
        ),
    ),
)
