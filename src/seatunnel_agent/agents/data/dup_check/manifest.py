"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="dup_check",
    workspace="data",
    route="/dupcheck",
    page_title="Dup Check",
    logo="DK",
    color="#b45309",
    title_en="Duplicate Check",
    title_zh="数据重复检测",
    desc_en="Full-row, primary-key and business-event duplicates with "
            "row spans and differing columns that locate the source",
    desc_zh="全行/主键/业务事件三层重复检测,重复组带首末行号与差异列,差异列定位来源",
    api="seatunnel_agent.agents.data.dup_check.api:router",
    group="quality",
    order=65,
    external=True,
    tools=(
        ToolManifest(
            name="dup_check",
            ref="seatunnel_agent.agents.data.dup_check.tools:dup_check",
            desc_zh="数据重复检测（三层重复组 + 差异列定位来源）",
            desc_en="Duplicate check (three layers + differing columns)",
            router_en="Check a pasted data sample (CSV with a header row, "
                      "or JSONL) for duplicates on three layers: "
                      "identical rows, repeated primary keys and repeated "
                      "business-event keys (declared comma-separated "
                      "columns). Groups report row counts, first/last "
                      "row numbers and the columns that differ inside a "
                      "key group — which points at the duplication "
                      "source: a retried load, upstream fan-out or a "
                      "missing dedup window.",
            keywords=("重复", "去重", "dup", "duplicate", "主键",
                      "重复主键", "重复数据", "dedup", "幂等", "多余行"),
        ),
    ),
)
