"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="config_migrate",
    workspace="data",
    route="/migrate",
    page_title="Config Migrate",
    logo="🚚",
    color="#0d9488",
    title_en="DataX/Sqoop Migration",
    title_zh="配置迁移 DataX/Sqoop",
    desc_en="Convert DataX job JSON / sqoop commands into SeaTunnel configs with a migration-notes list",
    desc_zh="DataX job JSON / sqoop 命令一键转 SeaTunnel 配置，附迁移说明清单",
    api="seatunnel_agent.agents.data.config_migrate.api:router",
    group="build",
    order=40,
    external=True,
)
