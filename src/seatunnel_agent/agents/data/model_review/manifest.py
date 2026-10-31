"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="model_review",
    workspace="data",
    route="/modelreview",
    page_title="Model Review",
    logo="MR",
    color="#7c2d12",
    title_en="Model Review",
    title_zh="建模体检",
    desc_en="Warehouse DDL — star-schema findings, graded: keyless "
            "dimensions, dimension-less facts, attributes leaked into "
            "or copied across facts, measure-less aggregates",
    desc_zh="数仓 DDL — 星型结构体检并分级:维表缺主键/事实表缺分区缺"
            "外键/维度属性混入或跨表复制/汇总表无度量/宽表",
    api="seatunnel_agent.agents.data.model_review.api:router",
    group="governance",
    order=92,
    external=True,
    tools=(
        ToolManifest(
            name="model_review",
            ref="seatunnel_agent.agents.data.model_review.tools:model_review",
            desc_zh="维度建模体检（DDL → 星型结构分级发现）",
            desc_en="Dimensional-model review (DDL → graded findings)",
            router_en="Review the star schema in warehouse CREATE TABLE "
                      "DDL: prefixes decide roles (dim / dwd·dws facts "
                      "/ ods·stg raw), then keyless dimensions grade "
                      "high; unpartitioned facts, facts with no *_id "
                      "column, descriptive attributes living in a fact, "
                      "attributes copied across facts and over-wide "
                      "tables grade medium; measure-less aggregates "
                      "grade low. Distinct from metadata_quality "
                      "(declaration conventions) and layer_check "
                      "(lineage layering). No database connection.",
            keywords=("建模", "维度", "星型", "model", "dimension",
                      "fact", "主键", "外键", "宽表", "度量"),
        ),
    ),
)
