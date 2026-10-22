"""Platform plugin manifest — see seatunnel_agent.hub.registry.

External: the route is the React app under frontend/uitest (mounted by the
launcher's external-app loop); the hub card lives on the landing page.
"""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="uitest",
    workspace="devops",
    route="/uitest",
    page_title="UI Testing",
    logo="UT",
    color="#f59e0b",
    title_en="UI Testing Agent",
    title_zh="UI 测试 Agent",
    desc_en="Browser-driven regression for the agent pages — YAML cases, LLM fuzzy assertions, HTML reports",
    desc_zh="真实浏览器驱动的页面自动回归 — YAML 用例、LLM 模糊断言、HTML 报告",
    api="seatunnel_agent.agents.devops.ui_testing.api:router",
    card=False,
    external=True,
)
