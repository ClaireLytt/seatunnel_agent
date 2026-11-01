"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="sql_perf",
    workspace="data",
    route="/sqlperf",
    page_title="SQL Perf",
    logo="EX",
    color="#b91c1c",
    title_en="Plan Analyzer",
    title_zh="执行计划分析",
    desc_en="Paste EXPLAIN output — joins, shuffles, partition pruning "
            "and pushdown, with prescriptions",
    desc_zh="粘贴 EXPLAIN 输出 — join、shuffle、分区裁剪与谓词下推，附处方",
    api="seatunnel_agent.agents.data.sql_perf.api:router",
    group="quality",
    order=15,
    external=True,
    tools=(
        ToolManifest(
            name="sql_perf",
            ref="seatunnel_agent.agents.data.sql_perf.tools:sql_perf",
            desc_zh="执行计划分析（EXPLAIN 文本 → join/shuffle/裁剪/下推发现与处方）",
            desc_en="Plan analysis (EXPLAIN text → findings and prescriptions)",
            router_en="Analyze an EXPLAIN / EXPLAIN FORMATTED output "
                      "(Spark or Hive): join types, shuffle count, per-scan "
                      "partition pruning and filter pushdown — findings "
                      "ranked by severity with concrete prescriptions "
                      "(cartesian joins, full-partition scans, missed "
                      "pushdown, excess shuffles, broadcast candidates).",
            keywords=("执行计划", "explain", "性能", "shuffle", "join",
                      "分区裁剪", "下推", "pushdown", "broadcast",
                      "performance", "慢", "优化"),
        ),
    ),
)
