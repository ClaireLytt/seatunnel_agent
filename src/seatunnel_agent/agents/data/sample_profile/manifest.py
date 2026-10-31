"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="sample_profile",
    workspace="data",
    route="/sampleprofile",
    page_title="Sample Profile",
    logo="SA",
    color="#0e7490",
    title_en="Sample Profiler",
    title_zh="数据抽样剖析",
    desc_en="Paste CSV/JSONL rows — stride sample, per-column kinds, "
            "null/unique rates, format buckets, anomaly findings",
    desc_zh="粘贴 CSV/JSONL 数据行 — 等距抽样、逐列类型/空值/唯一率/格式桶，异常发现带行号",
    api="seatunnel_agent.agents.data.sample_profile.api:router",
    group="quality",
    order=63,
    external=True,
    tools=(
        ToolManifest(
            name="sample_profile",
            ref="seatunnel_agent.agents.data.sample_profile.tools:sample_profile",
            desc_zh="数据抽样剖析（CSV/JSONL → 列剖面 + 异常发现）",
            desc_en="Sample profiler (CSV/JSONL → column profiles + findings)",
            router_en="Profile a pasted data sample (CSV with a header "
                      "row, or JSONL): deterministic stride sampling, "
                      "per-column type inference, null and unique rates, "
                      "numeric ranges, top values and format buckets, "
                      "with ranked anomaly findings — mixed types, high "
                      "nulls, constant columns, outlier formats with row "
                      "numbers, numbers stored as text, whitespace/case "
                      "drift.",
            keywords=("抽样", "剖析", "profile", "sample", "数据体检",
                      "字段", "格式", "空值", "混合类型", "脏数据",
                      "csv", "jsonl"),
        ),
    ),
)
