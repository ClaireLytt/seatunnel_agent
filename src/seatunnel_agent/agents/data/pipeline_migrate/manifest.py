"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="pipeline_migrate",
    workspace="data",
    route="/pipemigrate",
    page_title="Pipeline Migrate",
    logo="PM",
    color="#a16207",
    title_en="Migration Assessor",
    title_zh="Pipeline 迁移评估",
    desc_en="Legacy ETL scripts — target engine, effort size and the "
            "constructs that will not migrate mechanically",
    desc_zh="旧 ETL 脚本 — 目标引擎、工作量分级与无法机械翻译的语法",
    api="seatunnel_agent.agents.data.pipeline_migrate.api:router",
    group="build",
    order=45,
    external=True,
    tools=(
        ToolManifest(
            name="pipeline_migrate",
            ref="seatunnel_agent.agents.data.pipeline_migrate.tools:pipeline_migrate",
            desc_zh="Pipeline 迁移评估（旧 ETL 脚本 → 目标引擎、S/M/L 工作量与风险）",
            desc_en="Migration assessment (legacy ETL → target, effort, risks)",
            router_en="Assess migrating legacy ETL scripts to "
                      "SeaTunnel/Spark/Flink: scan a scripts directory (or "
                      "one script), suggest the target engine per job, size "
                      "the effort S/M/L from a transparent score, and list "
                      "constructs that cannot be translated mechanically.",
            keywords=("迁移", "migration", "migrate", "legacy", "etl",
                      "sqoop", "datax", "评估", "assessment", "工作量"),
        ),
    ),
)
