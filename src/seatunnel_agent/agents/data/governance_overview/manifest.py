"""Platform plugin manifest — see seatunnel_agent.hub.registry.

A page-only plugin: it aggregates the governance agents' run histories
through their own ``GET /stats`` endpoints, so it ships no API of its own.
"""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="governance_overview",
    workspace="data",
    route="/governance",
    page_title="Governance Overview",
    logo="GO",
    color="#166534",
    title_en="Governance Overview",
    title_zh="治理总览",
    desc_en="One page over the governance run histories: latest posture and trend per agent",
    desc_zh="五个治理 agent 的运行历史一页看完 — 最新状态与趋势",
    group="governance",
    order=49,
    external=True,
)
