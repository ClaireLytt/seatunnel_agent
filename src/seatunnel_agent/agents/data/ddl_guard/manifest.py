"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="ddl_guard",
    workspace="data",
    route="/ddlguard",
    page_title="Migration Guard",
    logo="🛡️",
    color="#0e7490",
    title_en="Migration Guard",
    title_zh="迁移守卫",
    desc_en="Grade dangerous DDL in migration scripts and generate the rollback, irreversible steps marked",
    desc_zh="迁移脚本危险操作分级 + 自动生成回滚脚本,不可逆步骤显式标注",
    api="seatunnel_agent.agents.data.ddl_guard.api:router",
    group="governance",
    order=55,
    external=True,
    tools=(
        ToolManifest(
            name="ddl_guard",
            ref="seatunnel_agent.agents.data.ddl_guard.tools:ddl_guard",
            desc_zh="迁移守卫（危险 DDL 分级 + 回滚脚本生成）",
            desc_en="Migration guard (graded dangerous DDL + generated rollback)",
            router_en="Grade dangerous operations in a DDL migration script "
                      "(drops, truncates, type narrowing, renames) and "
                      "generate the rollback script.",
            keywords=("回滚", "rollback", "迁移", "migration", "删表",
                      "drop table", "上线脚本", "ddl 变更"),
        ),
    ),
)
