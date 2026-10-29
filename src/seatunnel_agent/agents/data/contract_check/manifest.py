"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="contract_check",
    workspace="data",
    route="/contract",
    page_title="Data Contract",
    logo="📜",
    color="#4d7c0f",
    title_en="Data Contract",
    title_zh="数据契约校验",
    desc_en="Declared table promises vs actual DDL: missing columns, type and partition violations",
    desc_zh="声明的表承诺 vs 实际 DDL — 列缺失、类型与分区违约逐条报出",
    api="seatunnel_agent.agents.data.contract_check.api:router",
    group="governance",
    order=53,
    external=True,
    tools=(
        ToolManifest(
            name="contract_check",
            ref="seatunnel_agent.agents.data.contract_check.tools:contract_check",
            desc_zh="数据契约校验（YAML 承诺 vs 实际 DDL，违约分级）",
            desc_en="Data-contract check (YAML promises vs actual DDL, graded violations)",
            router_en="Check actual DDL against a declared YAML contract: "
                      "missing tables/columns, type and partition violations.",
            keywords=("契约", "contract", "数据契约", "表结构约定", "违约",
                      "schema contract"),
        ),
    ),
)
