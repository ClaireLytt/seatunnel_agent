"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="ddl_evolve",
    workspace="data",
    route="/ddlevolve",
    page_title="DDL Migration",
    logo="DE",
    color="#3f6212",
    title_en="DDL Migration",
    title_zh="DDL 迁移脚本",
    desc_en="Two DDL snapshots in, a migration script out — safe "
            "changes run as-is, destructive ones stay commented with a "
            "review note",
    desc_zh="新旧两版 DDL 快照 — 一键生成迁移脚本,安全变更可直接执行,"
            "危险变更保持注释并附评审提示",
    api="seatunnel_agent.agents.data.ddl_evolve.api:router",
    group="build",
    order=97,
    external=True,
    tools=(
        ToolManifest(
            name="ddl_evolve",
            ref="seatunnel_agent.agents.data.ddl_evolve.tools:ddl_evolve",
            desc_zh="DDL 迁移脚本生成（两版快照 → ALTER 脚本）",
            desc_en="DDL migration (two snapshots → ALTER script)",
            router_en="Turn a schema diff into an executable migration: "
                      "paste the old and new CREATE TABLE snapshots and "
                      "get ALTER/CREATE statements — widenings, added "
                      "columns, renames, comment updates and new tables "
                      "run as-is, while drops, narrowing type changes "
                      "and partition-layout changes are emitted "
                      "commented-out with a review note so nothing "
                      "destructive runs by accident. schema_drift "
                      "reports the diff; this ships the script. Hive "
                      "and MySQL spellings. No database connection.",
            # no 迁移/脚本/上线: those route ddl_guard's rollback-safety
            # checks (test_ddl_guard pins them); this tool's distinct
            # ask is generating ALTERs from two snapshots
            keywords=("ddl", "alter", "migration", "evolve", "表结构",
                      "快照", "生成", "加列", "改列"),
        ),
    ),
)
