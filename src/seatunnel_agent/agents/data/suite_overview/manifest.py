"""Platform plugin manifest — see seatunnel_agent.hub.registry.

A page-only plugin: a navigator over the agent suites added in the
36–54 batches.  It ships no API of its own — every card links to the
agent's own page.
"""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="suite_overview",
    workspace="data",
    route="/suites",
    page_title="Suite Overview",
    logo="SO",
    color="#1c1a17",
    title_en="Suite Overview",
    title_zh="套件总览",
    desc_en="One page over the quality, governance, realtime and "
            "scheduling suites — every agent, grouped and linked",
    desc_zh="质量/资产治理/实时链路/调度运维四个套件一页看完,按套件分组直达各 agent",
    group="quality",
    order=9,
    external=True,
)
