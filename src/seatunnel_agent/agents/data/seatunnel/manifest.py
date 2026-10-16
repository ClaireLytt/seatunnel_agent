"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="seatunnel",
    workspace="data",
    route="/seatunnel",
    page_title="SeaTunnel",
    logo="ST",
    color="#f76707",
    title_en="SeaTunnel Pipeline Builder",
    title_zh="SeaTunnel Pipeline Builder · 数据管道构建",
    desc_en="Generate / validate / run SeaTunnel configs with natural language, auto-diagnose & fix",
    desc_zh="自然语言生成 / 验证 / 运行 SeaTunnel 配置，自动诊断修复",
    render="seatunnel_agent.agents.data.seatunnel.ui:_render_seatunnel_page",
    group="build",
    order=10,
)
