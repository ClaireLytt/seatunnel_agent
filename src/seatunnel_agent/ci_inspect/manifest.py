# -*- coding: utf-8 -*-
"""Platform plugin manifest — see seatunnel_agent.registry."""

from ..registry import AgentManifest

MANIFEST = AgentManifest(
    name="ci_inspect",
    workspace="devops",
    route="/ciinspect",
    page_title="CI Log Triage",
    logo="CI",
    color="#2563eb",
    title_en="CI Log Triage",
    title_zh="CI 日志诊断",
    desc_en=("Cluster failed-job logs into root causes, spot flaky jobs and duration drift across runs"),
    desc_zh=("失败日志聚类出根因,识别 flaky 作业与时长漂移"),
    render="seatunnel_agent.ci_inspect_ui:render_ci_inspect_page",
    api="seatunnel_agent.ci_inspect.api:router",
    order=20,
)
