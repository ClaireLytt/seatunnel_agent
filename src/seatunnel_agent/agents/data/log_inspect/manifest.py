"""Platform plugin manifest — see seatunnel_agent.hub.registry.

Route only: the card lives on the hub landing page (engineering tools).
"""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="log_inspect",
    workspace="data",
    route="/loginspect",
    page_title="Log Inspect",
    logo="🧾",
    color="#7c3aed",
    title_en="Log Inspection",
    title_zh="批量日志巡检",
    desc_en="Exception clustering over a log directory — collapse noisy logs into Top-N root causes",
    desc_zh="日志目录异常聚类 — 把嘈杂日志收敛成 Top-N 个根因",
    api="seatunnel_agent.agents.data.log_inspect.api:router",
    external=True,
    card=False,
)
