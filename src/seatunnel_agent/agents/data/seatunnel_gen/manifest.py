"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="seatunnel_gen",
    workspace="data",
    route="/seatunnelgen",
    page_title="Job Draft",
    logo="JD",
    color="#0c4a6e",
    title_en="Job Draft",
    title_zh="作业配置生成",
    desc_en="Table DDL + a connector pair — a complete SeaTunnel "
            "job.conf, database and table filled from the DDL, "
            "placeholders named, linted clean before it leaves",
    desc_zh="表 DDL + 源目连接器 — 一键生成完整 SeaTunnel job.conf,"
            "库表按 DDL 填充/占位符点名/配置体检零错误出厂",
    api="seatunnel_agent.agents.data.seatunnel_gen.api:router",
    group="build",
    order=99,
    external=True,
    tools=(
        ToolManifest(
            name="seatunnel_gen",
            ref="seatunnel_agent.agents.data.seatunnel_gen.tools:seatunnel_gen",
            desc_zh="SeaTunnel 作业配置生成（DDL → job.conf 草稿）",
            desc_en="SeaTunnel job draft (DDL → linted job.conf)",
            router_en="Generate the first SeaTunnel job config nobody "
                      "wants to write by hand: paste the table's CREATE "
                      "TABLE DDL and name the source and sink "
                      "connectors (MySQL-CDC, Jdbc, Kafka, Doris, Hive, "
                      "ClickHouse, ...) — the draft emits a complete "
                      "env/source/sink HOCON with database/table/topic "
                      "filled from the table name, documented examples "
                      "for the rest (each listed as a placeholder), "
                      "STREAMING auto-selected for CDC sources, and a "
                      "config_lint pass guaranteeing zero errors. "
                      "config_lint checks configs; this writes them. No "
                      "database connection.",
            keywords=("seatunnel", "作业", "配置", "生成", "hocon",
                      "job.conf", "同步", "connector", "cdc", "草稿"),
        ),
    ),
)
