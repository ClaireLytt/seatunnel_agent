"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="cdc_diag",
    workspace="data",
    route="/cdcdiag",
    page_title="CDC Diag",
    logo="CD",
    color="#b45309",
    title_en="CDC Diagnosis",
    title_zh="CDC 同步诊断",
    desc_en="Replication snapshot — binlog lag, event stalls, retention "
            "data-loss risk, classified errors and broken resume points",
    desc_zh="同步快照 — binlog 落后/事件停滞/保留期丢数风险/错误分类/断点错乱,附处方",
    api="seatunnel_agent.agents.data.cdc_diag.api:router",
    group="quality",
    order=78,
    external=True,
    tools=(
        ToolManifest(
            name="cdc_diag",
            ref="seatunnel_agent.agents.data.cdc_diag.tools:cdc_diag",
            desc_zh="CDC 同步异常诊断（快照 JSON → 发现 + 处方）",
            desc_en="CDC sync diagnosis (snapshot → findings)",
            router_en="Diagnose a CDC/binlog sync pipeline from a pasted "
                      "snapshot (JSON with the source's binlog file/"
                      "position/retention and the consumer's coordinates, "
                      "last event time and recent errors — every section "
                      "optional): rules flag binlog files behind, byte "
                      "lag, event stalls, the retention-window data-loss "
                      "risk, classified errors (schema change / "
                      "duplicate key / connection) and a consumer ahead "
                      "of the source (broken resume point). No database "
                      "connection.",
            keywords=("cdc", "binlog", "同步", "offset", "断点", "丢数",
                      "复制", "replication", "停滞", "debezium",
                      "canal"),
        ),
    ),
)
