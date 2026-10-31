"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="kafka_lag",
    workspace="data",
    route="/kafkalag",
    page_title="Kafka Lag",
    logo="KL",
    color="#9f1239",
    title_en="Kafka Lag",
    title_zh="Kafka 消费积压",
    desc_en="Consumer-group snapshot — backlog, hot partitions, "
            "falling-behind and stalled partitions with catch-up ETAs",
    desc_zh="消费组快照 — 积压量级/热点分区/追不上/停滞分区,附追赶 ETA 与处方",
    api="seatunnel_agent.agents.data.kafka_lag.api:router",
    group="quality",
    order=75,
    external=True,
    tools=(
        ToolManifest(
            name="kafka_lag",
            ref="seatunnel_agent.agents.data.kafka_lag.tools:kafka_lag",
            desc_zh="Kafka 消费积压诊断（offset 快照 → 发现 + 处方）",
            desc_en="Kafka consumer-lag diagnosis (snapshot → findings)",
            router_en="Diagnose a Kafka consumer group from a pasted "
                      "offset snapshot (JSON topics/partitions with "
                      "log-end and committed offsets, optional consume/"
                      "produce rates, or CSV rows): rules flag the total "
                      "backlog, hot partitions far above the median lag, "
                      "partitions consuming slower than they produce "
                      "(never catching up), stalled partitions and slow "
                      "catch-up ETAs — each with a prescription. No "
                      "broker connection.",
            keywords=("kafka", "积压", "lag", "消费组", "consumer",
                      "offset", "分区", "backlog", "追不上", "停滞"),
        ),
    ),
)
