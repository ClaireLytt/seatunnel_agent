# -*- coding: utf-8 -*-
"""Platform plugin manifest — see seatunnel_agent.registry."""

from ..registry import AgentManifest

MANIFEST = AgentManifest(
    name="doctor",
    workspace="devops",
    route="/doctor",
    page_title="Doctor",
    logo="🩺",
    color="#059669",
    title_en="Environment Doctor",
    title_zh="环境医生",
    desc_en=("Describe the symptom — the agent checks ports, packages, LLM "
             "config and log tails (read-only), then prescribes the fix "
             "commands for you to run"),
    desc_zh=("描述症状 — agent 自己查端口、依赖、LLM 配置与日志尾部"
             "(全只读),给出修复命令由你执行"),
    render="seatunnel_agent.doctor_ui:render_doctor_page",
    api=None,  # it introspects the local environment — CLI/UI only
    order=50,
)
