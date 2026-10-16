"""Platform plugin manifest — see seatunnel_agent.hub.registry.

Route only: the card lives on the hub landing page (engineering tools).
"""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="mcp_toolbox",
    workspace="data",
    route="/mcp",
    page_title="MCP Toolbox",
    logo="MCP",
    color="#6366f1",
    title_en="MCP Toolbox",
    title_zh="MCP 工具箱",
    desc_en="The whole suite as one MCP server for Claude Code / Desktop — tools, client setup & call audit",
    desc_zh="整套 agent 一个 MCP server 交给 Claude Code / Desktop —— 工具清单、接入配置与调用审计",
    render="seatunnel_agent.agents.data.mcp_toolbox.ui:render_mcp_page",
    card=False,
)
