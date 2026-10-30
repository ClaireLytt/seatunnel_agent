"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="pipeline_doctor",
    workspace="data",
    route="/pipedoctor",
    page_title="Pipeline Doctor",
    logo="PD",
    color="#b91c1c",
    title_en="Pipeline Failure Diagnosis",
    title_zh="Pipeline 故障诊断",
    desc_en="Diagnose a failed Spark/Hive/SeaTunnel run — engine detection, "
            "failure-signature matching, root cause and fix",
    desc_zh="失败的 Spark/Hive/SeaTunnel 运行日志 — 识别引擎、匹配故障签名、"
            "定位根因并给出修复方案",
    api="seatunnel_agent.agents.data.pipeline_doctor.api:router",
    group="build",
    order=25,
    external=True,
    tools=(
        ToolManifest(
            name="pipeline_diagnose",
            ref="seatunnel_agent.agents.data.pipeline_doctor.tools:pipeline_diagnose",
            desc_zh="Pipeline 故障诊断（运行日志 → 根因 + 修复方案）",
            desc_en="Pipeline failure diagnosis (run log → root cause + fix)",
            router_en="Diagnose a failed Spark/Hive/SeaTunnel run from its "
                      "logs: detect the engine, match known failure "
                      "signatures, name the root cause and the fix.",
            keywords=("故障", "诊断", "失败", "报错", "diagnose", "failure",
                      "oom", "根因", "root cause", "日志"),
        ),
    ),
)
