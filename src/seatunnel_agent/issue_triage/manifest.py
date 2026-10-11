# -*- coding: utf-8 -*-
"""Platform plugin manifest — see seatunnel_agent.registry."""

from ..registry import AgentManifest

MANIFEST = AgentManifest(
    name="issue_triage",
    workspace="ai",
    route="/triage",
    page_title="Issue Triage",
    logo="🏷️",
    color="#9333ea",
    title_en="Issue Triage Agent",
    title_zh="Issue 分诊 Agent",
    desc_en=("Dedupe against issue history (BM25), locate the module "
             "(git grep), check the docs — then labels, priority and a "
             "draft reply"),
    desc_zh=("历史 issue 查重(BM25)、git grep 定位模块、查文档 — 产出"
             "标签、优先级与草拟回复"),
    render="seatunnel_agent.issue_triage_ui:render_issue_triage_page",
    api="seatunnel_agent.issue_triage.api:router",
    order=70,
)
