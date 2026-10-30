"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

MANIFEST = AgentManifest(
    name="doc_qa",
    workspace="ai",
    route="/docqa",
    page_title="Doc Q&A",
    logo="DQ",
    color="#0891b2",
    title_en="Doc Q&A",
    title_zh="文档问答",
    desc_en=("Ask the SeaTunnel connector & project docs — offline BM25 "
             "retrieval with citations, optional grounded LLM synthesis"),
    desc_zh=("SeaTunnel 连接器与项目文档问答 — 离线 BM25 检索带引用,"
             "可选基于片段的 LLM 综合"),
    api="seatunnel_agent.agents.ai.doc_qa.api:router",
    order=50,
    external=True,
)
