"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest

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
    external=True,
    api="seatunnel_agent.agents.devops.doctor.api:router",
    order=50,
)
