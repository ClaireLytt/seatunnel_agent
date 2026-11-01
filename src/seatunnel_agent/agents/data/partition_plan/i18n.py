"""EN/ZH strings for the partition-plan reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

PP_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Partition Plan",
        "rpt_scope": "**{cands}** candidate column(s) scored against "
                     "**{queries}** quer(ies)",
        "rpt_reco": "Recommendation",
        "rpt_no_reco": "No column qualifies as a partition key — see the "
                       "findings.",
        "rpt_cands": "Candidates (best first)",
        "col_column": "column",
        "col_kind": "kind",
        "col_distinct": "distinct",
        "col_hits": "WHERE hits",
        "col_score": "score",
        "col_verdict": "verdict",
        "v_recommend": "recommend",
        "v_possible": "possible",
        "v_unsuitable": "unsuitable",
        "r_time_filtered": "time-shaped and filtered — the canonical key",
        "r_time_shaped": "time-shaped, not filtered in this workload",
        "r_filtered": "filtered, not time-shaped",
        "r_unfiltered": "nothing in the workload filters on it",
        "r_single_value": "a single value partitions nothing",
        "r_too_many": "too many distinct values — would explode the "
                      "metastore",
        "rpt_findings": "Findings",
        "col_sev": "sev",
        "col_code": "code",
        "col_issue": "issue",
        "PP001": "no time-shaped column qualifies — at fact volume the "
                 "table will scan unpruned",
        "PP002": "the hottest filter column is unsuitable as a partition "
                 "key ({detail}) — bucket it instead",
        "PP003": "{detail} quer(ies) filter on no sampled column — "
                 "unprunable full scans whatever the key",
        "rpt_disclaimer": "> Scored on the pasted sample and workload "
                          "only — cardinality is the sample's, and a "
                          "workload window that misses the monthly jobs "
                          "undercounts their filters. partition_health "
                          "examines partitions a table already has; "
                          "this picks the key for one that has none.",
        "rpt_llm_note": "Plan review (LLM — review before DDL)",
    },
    "zh": {
        "rpt_title": "分区键选型",
        "rpt_scope": "**{cands}** 个候选列 × **{queries}** 条查询打分",
        "rpt_reco": "推荐",
        "rpt_no_reco": "没有列够格当分区键 — 见下方发现。",
        "rpt_cands": "候选（最优在前）",
        "col_column": "列",
        "col_kind": "类型",
        "col_distinct": "基数",
        "col_hits": "WHERE 命中",
        "col_score": "得分",
        "col_verdict": "结论",
        "v_recommend": "推荐",
        "v_possible": "可选",
        "v_unsuitable": "不适合",
        "r_time_filtered": "时间形且被过滤 — 经典分区键",
        "r_time_shaped": "时间形,本负载未过滤",
        "r_filtered": "被过滤,非时间形",
        "r_unfiltered": "负载里没人按它过滤",
        "r_single_value": "只有一个值,分了等于没分",
        "r_too_many": "基数过高 — 会撑爆元数据",
        "rpt_findings": "发现",
        "col_sev": "级",
        "col_code": "编码",
        "col_issue": "问题",
        "PP001": "没有够格的时间形列 — 事实量级下整表扫描无法裁剪",
        "PP002": "最热过滤列不适合当分区键（{detail}）— 改做分桶",
        "PP003": "{detail} 条查询不按任何采样列过滤 — 换什么键都裁不动",
        "rpt_disclaimer": "> 仅按粘贴样例与负载打分 — 基数是样例的基数,"
                          "负载窗口漏掉月度任务就会低估其过滤。"
                          "partition_health 体检已有分区,本页为还没分区"
                          "的表选键。",
        "rpt_llm_note": "选型评审（LLM — 落 DDL 前请复核）",
    },
}

tp = make_lookup(PP_I18N)
