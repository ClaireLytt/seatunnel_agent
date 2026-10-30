"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="issue_triage",
    workspace="ai",
    route="/triage",
    page_title="Issue Triage",
    logo="IT",
    color="#14b8a6",
    title_en="Issue Triage Agent",
    title_zh="Issue 分诊 Agent",
    desc_en=("Dedupe against issue history (BM25), locate the module "
             "(git grep), check the docs — then labels, priority and a "
             "draft reply"),
    desc_zh=("历史 issue 查重(BM25)、git grep 定位模块、查文档 — 产出"
             "标签、优先级与草拟回复"),
    api="seatunnel_agent.agents.ai.issue_triage.api:router",
    order=70,
    external=True,
)
