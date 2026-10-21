"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="orchestrator",
    workspace="ai",
    route="/orchestrator",
    page_title="Orchestrator",
    logo="AI",
    color="#b91c1c",
    title_en="Agent Orchestrator",
    title_zh="智能编排",
    desc_en=("One chat entry for the whole platform — the LLM routes your request to the right agents and chains steps"),
    desc_zh=("全平台统一对话入口 — LLM 自动路由到合适的 agent 并串联多步"),
    render="",
    api="seatunnel_agent.agents.ai.orchestrator.api:router",
    order=10,
    external=True,
)
