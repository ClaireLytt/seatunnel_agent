"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="compact_plan",
    workspace="data",
    route="/compactplan",
    page_title="Compaction Plan",
    logo="CP",
    color="#334155",
    title_en="Compaction Plan",
    title_zh="小文件治理",
    desc_en="A file inventory in, ranked merge candidates out — files "
            "freed per partition, NameNode pressure points named, "
            "templates ready",
    desc_zh="文件清单进,合并候选出 — 逐分区收敛文件数/NameNode 压力点"
            "点名/模板现成",
    api="seatunnel_agent.agents.data.compact_plan.api:router",
    group="governance",
    order=114,
    external=True,
    tools=(
        ToolManifest(
            name="compact_plan",
            ref="seatunnel_agent.agents.data.compact_plan.tools:"
                "compact_plan",
            desc_zh="小文件治理（文件清单 → 合并候选与模板）",
            desc_en="Compaction plan (file inventory → merge candidates)",
            router_en="Plan small-file compaction from a file inventory "
                      "(table, partition, file_count, total_mb): "
                      "partitions whose average file sits under the "
                      "threshold and hold 10+ files become merge "
                      "candidates ranked by the files they free, with "
                      "CONCATENATE / INSERT OVERWRITE templates; "
                      "1000-file partitions and tables whose small-file "
                      "share passes 25% are graded. partition_health "
                      "examines partition sizes; this examines the file "
                      "counts inside them. No cluster connection.",
            keywords=("小文件", "合并", "compaction", "concatenate",
                      "namenode", "文件数", "治理", "merge", "hdfs",
                      "收敛"),
        ),
    ),
)
