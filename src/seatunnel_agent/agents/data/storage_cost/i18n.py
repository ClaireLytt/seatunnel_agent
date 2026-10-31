"""EN/ZH strings for the storage-cost reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

SC_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Storage Cost Governance",
        "rpt_scope": "as of {today} · inventory **{total} GB** · "
                     "reclaimable or movable **{reclaim} GB** across "
                     "{n} action(s)",
        "rpt_actions": "Actions (biggest wins first)",
        "col_kind": "action",
        "col_table": "table",
        "col_freed": "GB freed/moved",
        "col_sev": "severity",
        "col_detail": "evidence",
        "kind_cold_tier": "move to cold tier",
        "kind_drop_partitions": "drop expired partitions",
        "kind_compact": "compact small files",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "d_cold": "untouched {days} day(s), {deps} downstream",
        "d_cold_nodate": "no recorded access, {deps} downstream",
        "d_drop": "{count} partition(s) past {retention}d retention, "
                  "oldest {oldest}",
        "d_compact": "avg file {avg} MB < {threshold} MB",
        "rpt_clean": "Nothing to reclaim — the inventory looks lean.",
        "rpt_disclaimer": "> Deterministic rules: cold tier needs >=100 "
                          "GB, zero 30-day access and >90 untouched "
                          "days; expired partitions by date-shaped "
                          "values vs the retention window; compaction "
                          "under 16 MB average files. Verify downstream "
                          "consumers before dropping anything.",
        "rpt_llm_note": "Governance note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "存储成本治理",
        "rpt_scope": "截至 {today} · 清单总量 **{total} GB** · "
                     "可释放/可迁移 **{reclaim} GB**（{n} 条动作）",
        "rpt_actions": "动作清单（收益大在前）",
        "col_kind": "动作",
        "col_table": "表",
        "col_freed": "释放/迁移 GB",
        "col_sev": "级别",
        "col_detail": "证据",
        "kind_cold_tier": "迁冷存储",
        "kind_drop_partitions": "清理过期分区",
        "kind_compact": "小文件合并",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "d_cold": "{days} 天未访问，下游 {deps} 个",
        "d_cold_nodate": "无访问记录，下游 {deps} 个",
        "d_drop": "{count} 个分区超出 {retention} 天保留期，"
                  "最老 {oldest}",
        "d_compact": "平均文件 {avg} MB < {threshold} MB",
        "rpt_clean": "无可治理项 — 清单很干净。",
        "rpt_disclaimer": "> 确定性规则：迁冷需 >=100 GB、30 天零访问且 "
                          ">90 天未动；过期分区按日期形态分区值 × 保留"
                          "窗口判定；平均文件 <16 MB 建议合并。清理前"
                          "务必确认下游消费方。",
        "rpt_llm_note": "治理通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(SC_I18N)
