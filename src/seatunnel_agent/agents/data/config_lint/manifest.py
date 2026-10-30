"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="config_lint",
    workspace="data",
    route="/conflint",
    page_title="Config Lint",
    logo="CL",
    color="#ea580c",
    title_en="Config Lint",
    title_zh="配置深度检查",
    desc_en="Param-level lint of SeaTunnel configs vs the built-in connector docs — typos get did-you-mean",
    desc_zh="对照内置连接器文档做参数级检查 — 拼错参数给「是不是想写」建议",
    api="seatunnel_agent.agents.data.config_lint.api:router",
    group="build",
    order=50,
    external=True,
)
