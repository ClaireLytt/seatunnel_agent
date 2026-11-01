"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="schema_align",
    workspace="data",
    route="/schemaalign",
    page_title="Schema Align",
    logo="SG",
    color="#0e7490",
    title_en="Schema Align",
    title_zh="源目对齐体检",
    desc_en="Source DDL vs sink DDL — dropped columns, NOT NULL traps, "
            "narrowings and risky conversions before the sync ships",
    desc_zh="源表 DDL × 目标表 DDL — 丢列/NOT NULL 陷阱/类型收窄/危险转换,上线前一贴体检",
    api="seatunnel_agent.agents.data.schema_align.api:router",
    group="build",
    order=88,
    external=True,
    tools=(
        ToolManifest(
            name="schema_align",
            ref="seatunnel_agent.agents.data.schema_align.tools:schema_align",
            desc_zh="源目 Schema 对齐（双 DDL → 映射风险分级）",
            desc_en="Schema alignment (two DDLs → mapping risks)",
            router_en="Judge a sync job's source-to-sink column mapping "
                      "from the two CREATE TABLE DDLs (MySQL/Hive/Doris "
                      "spellings parse): columns missing in the sink "
                      "(silently dropped), extra NOT NULL sink columns "
                      "without defaults (inserts fail), type narrowings "
                      "(bigint→int, decimal precision loss, varchar "
                      "truncation), risky string→number/time "
                      "conversions, timestamp→date truncation and "
                      "nullable→NOT NULL traps — widenings pass "
                      "silently. No database connection.",
            keywords=("schema", "对齐", "同步", "类型", "ddl", "映射",
                      "丢列", "截断", "精度", "sink", "cdc"),
        ),
    ),
)
