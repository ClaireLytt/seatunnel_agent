"""EN/ZH strings for slow-query diagnoses."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

SLOWQ_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Slow-Query Root Cause",
        "rpt_run": "run `{name}` took **{dur}**",
        "rpt_regression": " — **{reg}x** the baseline median ({base})",
        "rpt_causes": "Likely causes (largest share first)",
        "rpt_col_code": "code",
        "rpt_col_share": "share",
        "rpt_col_detail": "evidence",
        "rpt_col_rx": "prescription",
        "SQ001": "data skew — one straggler task holds the stage; run the "
                 "Data Skew agent on the SQL",
        "SQ002": "scan blow-up vs history — partition filter lost or data "
                 "grew; check the plan in the Plan Analyzer",
        "SQ003": "shuffle spill — memory per task too small for the "
                 "exchange; size it with the Cost Estimator",
        "SQ004": "GC pressure — heap too small or object churn; raise "
                 "executor memory / tune serialization",
        "SQ005": "queue wait — the cluster was busy; deconflict the "
                 "schedule (DAG Conflict agent)",
        "SQ006": "small files — too many tiny tasks; compact the input "
                 "or coalesce partitions",
        "rpt_none": "No rule fired — the run looks uniformly slow; "
                    "compare the plan against a fast run.",
        "rpt_disclaimer": ("> Deterministic rules over the submitted "
                           "metrics; shares are estimates for ranking, "
                           "not an accounting identity. No cluster "
                           "connection."),
        "rpt_incident_note": "Incident note draft (LLM — review before "
                             "sending)",
        "rpt_trend": ("**Creeping slowdown** — the last {runs} ledger "
                      "runs rose every time: {from_s} -> {to_s} "
                      "(+{growth_pct}%). Each step passed the per-run "
                      "gate; the trend did not."),
    },
    "zh": {
        "rpt_title": "慢查询根因",
        "rpt_run": "运行 `{name}` 耗时 **{dur}**",
        "rpt_regression": " — 为基线中位数（{base}）的 **{reg}x**",
        "rpt_causes": "可能的根因（按占比排序）",
        "rpt_col_code": "编号",
        "rpt_col_share": "占比",
        "rpt_col_detail": "证据",
        "rpt_col_rx": "处方",
        "SQ001": "数据倾斜 — 单个拖尾任务拖住整个 stage；把 SQL 交给数据倾斜 agent",
        "SQ002": "扫描量对比历史暴涨 — 分区过滤丢失或数据增长；用执行计划分析页核对",
        "SQ003": "shuffle 溢写 — 单任务内存撑不住交换；用资源预测页重新定容",
        "SQ004": "GC 压力 — 堆太小或对象翻腾；调大 executor 内存 / 序列化调优",
        "SQ005": "排队等待 — 集群当时很忙；用并发冲突 agent 错峰",
        "SQ006": "小文件 — 任务多而小；合并输入或 coalesce 分区",
        "rpt_none": "没有规则命中 — 整体均匀地慢；建议与一次快跑的计划对比。",
        "rpt_disclaimer": ("> 对提交指标的确定性规则判定；占比用于排序估计，"
                           "不构成会计恒等式。不连集群。"),
        "rpt_incident_note": "慢查询通报草稿（LLM 生成 — 发出前请审阅）",
        "rpt_trend": ("**慢化趋势** — 台账最近 {runs} 次运行逐次上涨：{from_s} "
                      "-> {to_s}（+{growth_pct}%）。每一步都没触发单次回归"
                      "闸门，但趋势在涨。"),
    },
}


tp = make_lookup(SLOWQ_I18N)
