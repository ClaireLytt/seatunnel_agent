"""EN/ZH strings for the Flink-diagnosis reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

FD_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Flink Job Diagnosis",
        "rpt_scope": "job `{job}` · sections seen: {sections} · **{n}** "
                     "finding(s)",
        "rpt_findings": "Findings (worst first)",
        "col_code": "code",
        "col_sev": "severity",
        "col_detail": "evidence",
        "col_rx": "prescription",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "FD001": "checkpoint failures — {failed}/{total}, latest failed: "
                 "{latest_failed}",
        "FD002": "checkpoint duration blow-up — last {last_ms:g}ms vs "
                 "median {median_ms}ms ({ratio}x)",
        "FD003": "alignment-dominated checkpoint — {alignment_ms:g}ms of "
                 "{duration_ms:g}ms ({share_pct}%)",
        "FD004": "backpressure — operator `{operator}` at "
                 "{backpressure:g} ({count} operator(s) pressured)",
        "FD005": "watermark lag — operator `{operator}` is "
                 "{watermark_lag_ms:g}ms behind ({count} operator(s))",
        "FD006": "restart churn — {count_1h} restart(s) in the last "
                 "hour; last cause: {last_cause}",
        "rx_FD001": "read the failure cause on the checkpoint page — "
                    "usually a timeout under backpressure or lost state "
                    "storage",
        "rx_FD002": "state grew or a barrier crawls through a pressured "
                    "operator — check FD004 first, then state TTL",
        "rx_FD003": "enable unaligned checkpoints or raise "
                    "max-concurrent-checkpoints; alignment is the cost "
                    "of backpressure",
        "rx_FD004": "find what the operator waits on: source backlog "
                    "(`seatunnel-agent kafkalag`) or skewed keys "
                    "(`seatunnel-agent skew-runtime`)",
        "rx_FD005": "an idle partition or a stuck source holds the "
                    "watermark — set an idleness timeout on the source",
        "rx_FD006": "stabilize before tuning: read the last cause; "
                    "OOM/TaskManager-lost points at memory sizing",
        "rpt_clean": "No rule fired — the job looks healthy.",
        "rpt_disclaimer": "> Deterministic rules over the pasted "
                          "snapshot: checkpoint 60/300s or 2x the "
                          "median, alignment share 50%, backpressure "
                          "0.5/0.8, watermark lag 60/300s, restarts "
                          "1/3 per hour. No cluster connection.",
        "rpt_llm_note": "Ops note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "Flink 作业诊断",
        "rpt_scope": "作业 `{job}` · 快照包含：{sections} · **{n}** 条发现",
        "rpt_findings": "发现（严重在前）",
        "col_code": "编码",
        "col_sev": "级别",
        "col_detail": "证据",
        "col_rx": "处方",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "FD001": "checkpoint 失败 — {failed}/{total}，最近一次失败："
                 "{latest_failed}",
        "FD002": "checkpoint 时长暴涨 — 最近 {last_ms:g}ms，此前中位数 "
                 "{median_ms}ms（{ratio} 倍）",
        "FD003": "对齐耗时主导 — {duration_ms:g}ms 里对齐占 "
                 "{alignment_ms:g}ms（{share_pct}%）",
        "FD004": "背压 — 算子 `{operator}` 背压 {backpressure:g}"
                 "（共 {count} 个算子受压）",
        "FD005": "watermark 滞后 — 算子 `{operator}` 落后 "
                 "{watermark_lag_ms:g}ms（共 {count} 个）",
        "FD006": "频繁重启 — 最近一小时 {count_1h} 次；最后原因："
                 "{last_cause}",
        "rx_FD001": "到 checkpoint 页看失败原因 — 通常是背压下超时或"
                    "状态存储丢失",
        "rx_FD002": "状态变大或 barrier 在受压算子里爬行 — 先看 FD004，"
                    "再查状态 TTL",
        "rx_FD003": "开 unaligned checkpoint 或调大并发 checkpoint 数；"
                    "对齐耗时是背压的账单",
        "rx_FD004": "找算子在等什么：源端积压（`seatunnel-agent "
                    "kafkalag`）或键倾斜（`seatunnel-agent "
                    "skew-runtime`）",
        "rx_FD005": "空闲分区或卡死的 source 拖住了 watermark — 给 "
                    "source 配 idleness 超时",
        "rx_FD006": "先稳住再调优：看最后原因；OOM/TaskManager 丢失指向"
                    "内存配置",
        "rpt_clean": "未命中任何规则 — 作业看起来健康。",
        "rpt_disclaimer": "> 对粘贴快照的确定性规则：checkpoint 60/300s "
                          "或 2 倍中位数、对齐占比 50%、背压 0.5/0.8、"
                          "watermark 滞后 60/300s、重启 1/3 次每小时。"
                          "不连集群。",
        "rpt_llm_note": "运维通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(FD_I18N)
