"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="dup_pipeline",
    workspace="data",
    route="/duppipeline",
    page_title="Dup Pipelines",
    logo="DP",
    color="#854d0e",
    title_en="Dup Pipelines",
    title_zh="重复建设检测",
    desc_en="Pipeline SQL — targets built twice from the same sources, "
            "subset-derivation candidates and hot sources missing a "
            "middle layer, graded",
    desc_zh="流水线 SQL — 同源双建/子集派生候选/源表高扇出缺中间层,"
            "逐项分级,双倍算力双倍漂移提前抓",
    api="seatunnel_agent.agents.data.dup_pipeline.api:router",
    group="governance",
    order=93,
    external=True,
    tools=(
        ToolManifest(
            name="dup_pipeline",
            ref="seatunnel_agent.agents.data.dup_pipeline.tools:dup_pipeline",
            desc_zh="重复建设检测（流水线 SQL → 同源双建分级发现）",
            desc_en="Duplicate-pipeline detection (SQL → graded overlaps)",
            router_en="Find duplicate warehouse builds in pasted "
                      "pipeline SQL: write targets reading the exact "
                      "same source set grade high when their output "
                      "expressions also overlap (same table built "
                      "twice) and medium on inputs alone; a target "
                      "whose sources are a proper subset of another's "
                      "is a derivation candidate; a source read "
                      "directly by many targets flags a missing middle "
                      "layer. Distinct from dup_check (duplicate rows "
                      "in data) and data_comparison (comparing table "
                      "contents). No database connection.",
            keywords=("重复", "建设", "dup", "pipeline", "收敛", "血缘",
                      "中间层", "合并", "治理", "扇出"),
        ),
    ),
)
