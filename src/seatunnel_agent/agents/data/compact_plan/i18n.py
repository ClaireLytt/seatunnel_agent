"""EN/ZH strings for the compaction-plan reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

CP_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Compaction Plan",
        "rpt_scope": "**{parts}** partition(s), **{files}** file(s) · "
                     "merging frees **{freed}** file(s) · ● {high} / "
                     "◐ {medium}",
        "rpt_cands": "Merge candidates (most files freed first)",
        "col_table": "table",
        "col_partition": "partition",
        "col_files": "files",
        "col_avg": "avg MB",
        "col_after": "after",
        "col_freed": "freed",
        "rpt_sql": "Templates (first {n})",
        "rpt_findings": "Findings",
        "col_sev": "sev",
        "col_code": "code",
        "col_issue": "issue",
        "CP001": "{value:.0%} of this table's files sit in small-file "
                 "partitions — schedule the compaction",
        "CP002": "partition {detail} holds {value:g} files — a NameNode "
                 "pressure point on its own",
        "rpt_clean": "No partition needs compaction.",
        "rpt_disclaimer": "> Planned from the pasted inventory only — a "
                          "partition is small-file when its average "
                          "file is under the threshold AND it holds "
                          "more than 10 files; tiny-but-few partitions "
                          "are left alone. Run merges off-peak and "
                          "verify row counts after. partition_health "
                          "examines sizes; this examines the file "
                          "counts inside them.",
        "rpt_llm_note": "Compaction review (LLM — review before running)",
    },
    "zh": {
        "rpt_title": "小文件治理",
        "rpt_scope": "**{parts}** 个分区、**{files}** 个文件 · 合并可收敛 "
                     "**{freed}** 个文件 · ● {high} / ◐ {medium}",
        "rpt_cands": "合并候选（收敛最多在前）",
        "col_table": "表",
        "col_partition": "分区",
        "col_files": "文件数",
        "col_avg": "均值 MB",
        "col_after": "合并后",
        "col_freed": "收敛",
        "rpt_sql": "模板（前 {n} 个）",
        "rpt_findings": "发现",
        "col_sev": "级",
        "col_code": "编码",
        "col_issue": "问题",
        "CP001": "该表 {value:.0%} 的文件落在小文件分区里 — 排期合并",
        "CP002": "分区 {detail} 有 {value:g} 个文件 — 单个分区就是一个 "
                 "NameNode 压力点",
        "rpt_clean": "没有分区需要合并。",
        "rpt_disclaimer": "> 只按粘贴清单规划 — 小文件分区 = 均值低于"
                          "阈值且文件数 >10,小而少的分区不动。合并放"
                          "低峰跑,跑完核对行数。partition_health 管分区"
                          "大小,本页管分区里的文件数。",
        "rpt_llm_note": "合并评审（LLM — 执行前请复核）",
    },
}

tp = make_lookup(CP_I18N)
