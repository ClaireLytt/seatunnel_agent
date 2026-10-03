# -*- coding: utf-8 -*-
"""Platform plugin manifest — see seatunnel_agent.registry."""

from ..registry import AgentManifest

MANIFEST = AgentManifest(
    name="doc_qa",
    workspace="ai",
    route="/docqa",
    page_title="Doc Q&A",
    logo="📖",
    color="#0891b2",
    title_en="Doc Q&A",
    title_zh="文档问答",
    desc_en=("Ask the SeaTunnel connector & project docs — offline BM25 "
             "retrieval with citations, optional grounded LLM synthesis"),
    desc_zh=("SeaTunnel 连接器与项目文档问答 — 离线 BM25 检索带引用,"
             "可选基于片段的 LLM 综合"),
    render="seatunnel_agent.doc_qa_ui:render_doc_qa_page",
    api="seatunnel_agent.doc_qa.api:router",
    order=50,
)
