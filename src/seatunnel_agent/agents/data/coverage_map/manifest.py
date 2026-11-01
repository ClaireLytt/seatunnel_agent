"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="coverage_map",
    workspace="data",
    route="/coveragemap",
    page_title="Coverage Map",
    logo="CM",
    color="#3b2f2f",
    title_en="Coverage Map",
    title_zh="质量覆盖地图",
    desc_en="DDL times the configured gates — which tables ship "
            "unguarded, which gates guard nothing, and the coverage "
            "share",
    desc_zh="DDL × 已配置的闸 — 谁在裸奔/哪道闸守着空城/总体覆盖率,"
            "补洞先后一图定",
    api="seatunnel_agent.agents.data.coverage_map.api:router",
    group="governance",
    order=110,
    external=True,
    tools=(
        ToolManifest(
            name="coverage_map",
            ref="seatunnel_agent.agents.data.coverage_map.tools:"
                "coverage_map",
            desc_zh="质量覆盖地图（DDL × DQC 规则/契约 → 裸奔表）",
            desc_en="Coverage map (DDL x gates → unguarded tables)",
            router_en="Map which warehouse tables are actually "
                      "protected: paste the CREATE TABLE DDL plus the "
                      "configured DQC rules YAML and/or contract YAML, "
                      "and every table shows its gates (row_count, "
                      "null_rate, unique, enum_domain, contract). "
                      "Unguarded tables grade medium (high in the "
                      "dwd/dws/ads layers consumers feel), gates naming "
                      "tables absent from the DDL are flagged as dead, "
                      "and the overall coverage share heads the report. "
                      "dq_rulegen and contract_gen draft what is "
                      "missing. No database connection.",
            keywords=("覆盖", "coverage", "裸奔", "质量", "闸", "地图",
                      "盘点", "gate", "unguarded", "死闸"),
        ),
    ),
)
