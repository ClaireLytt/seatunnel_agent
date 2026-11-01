"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="flink_diag",
    workspace="data",
    route="/flinkdiag",
    page_title="Flink Diag",
    logo="FD",
    color="#0e7490",
    title_en="Flink Diagnosis",
    title_zh="Flink 作业诊断",
    desc_en="Job snapshot — checkpoint failures and blow-ups, "
            "backpressure, watermark lag and restart churn with "
            "prescriptions",
    desc_zh="作业快照 — checkpoint 失败/暴涨/对齐主导、背压、watermark 滞后、频繁重启,附处方",
    api="seatunnel_agent.agents.data.flink_diag.api:router",
    group="quality",
    order=76,
    external=True,
    tools=(
        ToolManifest(
            name="flink_diag",
            ref="seatunnel_agent.agents.data.flink_diag.tools:flink_diag",
            desc_zh="Flink 作业诊断（快照 JSON → 发现 + 处方）",
            desc_en="Flink job diagnosis (snapshot → findings)",
            router_en="Diagnose a Flink job from a pasted snapshot (JSON "
                      "with checkpoints, operators' backpressure and "
                      "watermark lag, restart counts — every section "
                      "optional): rules flag checkpoint failures, "
                      "duration blow-ups vs the median, "
                      "alignment-dominated checkpoints (the unaligned-"
                      "checkpoint smell), backpressured operators, "
                      "watermark lag and restart churn — each with a "
                      "prescription pointing at kafka_lag or "
                      "skew-runtime. No cluster connection.",
            keywords=("flink", "checkpoint", "背压", "backpressure",
                      "watermark", "反压", "重启", "诊断", "实时",
                      "作业"),
        ),
    ),
)
