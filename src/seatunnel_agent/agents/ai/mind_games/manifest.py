"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="mind_games",
    workspace="ai",
    route="/games",
    page_title="Mind Games",
    logo="🎲",
    color="#0f766e",
    title_en="Mind Games",
    title_zh="心理小游戏",
    desc_en="Learned optimism, signature strengths and the five PERMA questions - all in the browser",
    desc_zh="乐观解释风格、品格优势与 PERMA 五问 — 全部在浏览器本地运行",
    order=90,
    external=True,
)
