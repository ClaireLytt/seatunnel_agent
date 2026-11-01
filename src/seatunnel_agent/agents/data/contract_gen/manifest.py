"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="contract_gen",
    workspace="data",
    route="/contractgen",
    page_title="Contract Draft",
    logo="CG",
    color="#166534",
    title_en="Contract Draft",
    title_zh="契约草稿生成",
    desc_en="CREATE TABLE DDL — a contract_check-ready YAML draft of "
            "what each table already promises: columns, types, "
            "partitions, comment discipline",
    desc_zh="CREATE TABLE DDL — 一键生成契约体检可直接消费的 contract "
            "YAML 草稿:列与类型/分区/注释纪律,只承诺已做到的",
    api="seatunnel_agent.agents.data.contract_gen.api:router",
    group="governance",
    order=90,
    external=True,
    tools=(
        ToolManifest(
            name="contract_gen",
            ref="seatunnel_agent.agents.data.contract_gen.tools:contract_gen",
            desc_zh="数据契约草稿生成（DDL → contract YAML）",
            desc_en="Contract draft generator (DDL → contract YAML)",
            router_en="Draft a data contract from CREATE TABLE DDL: "
                      "every data column with its type, the partition "
                      "layout, and the comment rule the table already "
                      "keeps (require_comments when coverage is high, "
                      "otherwise pin only existing comments). The YAML "
                      "round-trips through the contract_check parser so "
                      "it gates as-is. Use when a team wants to start "
                      "contract-gating tables but no contract exists "
                      "yet. No database connection.",
            keywords=("contract", "契约", "yaml", "ddl", "生成", "草稿",
                      "承诺", "gate", "schema", "注释"),
        ),
    ),
)
