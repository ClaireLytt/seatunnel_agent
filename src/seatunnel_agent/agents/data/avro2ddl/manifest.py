"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="avro2ddl",
    workspace="data",
    route="/avro2ddl",
    page_title="Avro to DDL",
    logo="AD",
    color="#4c1d1d",
    title_en="Avro to DDL",
    title_zh="消息 Schema 建表",
    desc_en="An Avro record or JSON Schema in, the landing CREATE TABLE "
            "out — logical types mapped, lossy rows named, parses clean",
    desc_zh="Avro record / JSON Schema 进,落地建表语句出 — logicalType "
            "对号入座,有损行点名,解析零错误",
    api="seatunnel_agent.agents.data.avro2ddl.api:router",
    group="build",
    order=112,
    external=True,
    tools=(
        ToolManifest(
            name="avro2ddl",
            ref="seatunnel_agent.agents.data.avro2ddl.tools:avro2ddl",
            desc_zh="消息 Schema 建表（Avro/JSON Schema → CREATE TABLE）",
            desc_en="Schema to DDL (Avro/JSON Schema → CREATE TABLE)",
            router_en="Land a topic as a table without hand-typing the "
                      "DDL: paste the Avro record (or JSON Schema) and "
                      "get the Hive or Doris CREATE TABLE — logicalType "
                      "wins (decimal/date/timestamp), [null,T] unions "
                      "unwrap as nullable, multi-type unions land as "
                      "STRING and are named, Hive gets real ARRAY/MAP/"
                      "STRUCT while Doris gets JSON plus a key/bucket "
                      "stub, doc becomes COMMENT. The DDL round-trips "
                      "through the schema parser. topic_schema diffs "
                      "two versions; this lands one; seatunnel_gen "
                      "turns the table into the sync job. No registry "
                      "or database connection.",
            keywords=("avro", "建表", "ddl 生成", "landing", "落地",
                      "json schema", "类型映射", "doris", "hive 表",
                      "接入"),
        ),
    ),
)
