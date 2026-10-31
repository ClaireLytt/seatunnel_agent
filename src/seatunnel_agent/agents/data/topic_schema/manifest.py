"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="topic_schema",
    workspace="data",
    route="/topicschema",
    page_title="Topic Schema Diff",
    logo="TS",
    color="#581c0c",
    title_en="Topic Schema Diff",
    title_zh="消息 Schema 对比",
    desc_en="Two Avro or JSON Schema versions — registry-grade "
            "compatibility verdicts per field, before the publish gets "
            "rejected",
    desc_zh="两版 Avro / JSON Schema — 按注册中心规则逐字段判兼容,发布"
            "被拒之前先看结论",
    api="seatunnel_agent.agents.data.topic_schema.api:router",
    group="build",
    order=106,
    external=True,
    tools=(
        ToolManifest(
            name="topic_schema_diff",
            ref="seatunnel_agent.agents.data.topic_schema.tools:"
                "topic_schema_diff",
            desc_zh="消息 Schema 兼容对比（两版 Avro/JSON Schema）",
            desc_en="Topic schema compatibility (Avro/JSON Schema)",
            router_en="Check a Kafka topic's schema change before the "
                      "registry rejects it: paste the old and new Avro "
                      "record or JSON Schema and every field change is "
                      "graded by compatibility mode — BACKWARD (new "
                      "schema reads old data; adding a defaultless "
                      "field breaks it), FORWARD (old readers survive "
                      "new data; removing a defaultless field breaks "
                      "it), or full for both; type changes pass only "
                      "along Avro promotions or a union widening by "
                      "null. schema_drift reads SQL DDL; this reads the "
                      "messaging world's schemas. No registry "
                      "connection.",
            keywords=("avro", "kafka", "topic", "兼容", "registry",
                      "json schema", "消息", "backward", "forward",
                      "发布"),
        ),
    ),
)
