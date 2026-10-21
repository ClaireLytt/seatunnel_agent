"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="web_task",
    workspace="ai",
    route="/webtask",
    page_title="Web Task Agent",
    logo="🖱️",
    color="#f97316",
    title_en="Web Task Agent",
    title_zh="网页操作 Agent",
    desc_en=("Goal + URL → a real browser loop: snapshot, click, fill, "
             "observe — confined to the start origin by default"),
    desc_zh=("给目标和 URL → 真实浏览器循环:快照、点击、填表、再观察 — "
             "默认只允许同源页面"),
    render="",
    external=True,
    # The run endpoint drives a local browser, so it is OFF by default:
    # 403 unless WEBTASK_API_ENABLED=1 is set.
    api="seatunnel_agent.agents.ai.web_task.api:router",
    order=80,
)
