"""EN/ZH strings for the Kafka-lag reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

KL_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Kafka Consumer-Lag Diagnosis",
        "rpt_scope": "group `{group}` · **{parts}** partition(s) · total "
                     "lag **{total}**",
        "rpt_findings": "Findings (worst first)",
        "col_code": "code",
        "col_sev": "severity",
        "col_detail": "evidence",
        "col_rx": "prescription",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "KL001": "large backlog — {total_lag} messages across "
                 "{partitions} partition(s)",
        "KL002": "hot partition — {topic}[{partition}] lag {lag} is "
                 "{ratio}x the median ({median_lag})",
        "KL003": "falling behind — {count} partition(s) consume slower "
                 "than they produce: {top}",
        "KL004": "stalled partition — {topic}[{partition}] has lag {lag} "
                 "and zero consume rate",
        "KL005": "slow catch-up — {topic}[{partition}] needs ~{eta_min} "
                 "min at current rates",
        "rx_KL001": "scale consumers up to the partition count before "
                    "anything else",
        "rx_KL002": "a key hotspot or one stuck consumer — check the "
                    "partition key distribution and that member's host",
        "rx_KL003": "throughput deficit — raise max.poll.records / "
                    "parallelism, or the lag only grows",
        "rx_KL004": "the assigned consumer is dead or wedged — check "
                    "rebalance logs and the member host",
        "rx_KL005": "acceptable if a backfill is draining; otherwise "
                    "add temporary consumers",
        "rpt_partitions": "Top partitions by lag",
        "col_topic": "topic[partition]",
        "col_lag": "lag",
        "col_offsets": "committed → end",
        "col_rates": "consume/produce per s",
        "rpt_clean": "No rule fired — the group is keeping up.",
        "rpt_disclaimer": "> Deterministic rules over the pasted "
                          "snapshot: backlog 100k/1M, hot partition "
                          "5x/20x the median, catch-up ETA 30/180 min. "
                          "Rates are optional; rate rules stay quiet "
                          "without them. No broker connection.",
        "rpt_llm_note": "Ops note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "Kafka 消费积压诊断",
        "rpt_scope": "消费组 `{group}` · **{parts}** 个分区 · 总积压 "
                     "**{total}**",
        "rpt_findings": "发现（严重在前）",
        "col_code": "编码",
        "col_sev": "级别",
        "col_detail": "证据",
        "col_rx": "处方",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "KL001": "积压量大 — {partitions} 个分区共 {total_lag} 条",
        "KL002": "热点分区 — {topic}[{partition}] 积压 {lag}，是中位数"
                 "（{median_lag}）的 {ratio} 倍",
        "KL003": "追不上 — {count} 个分区消费速率低于生产：{top}",
        "KL004": "停滞分区 — {topic}[{partition}] 积压 {lag} 且消费"
                 "速率为 0",
        "KL005": "追赶偏慢 — {topic}[{partition}] 按当前速率需约 "
                 "{eta_min} 分钟",
        "rx_KL001": "先把消费者数量加到分区数，再谈别的",
        "rx_KL002": "键热点或单个消费者卡住 — 查分区键分布与该成员所在"
                    "机器",
        "rx_KL003": "吞吐缺口 — 提高 max.poll.records/并行度，否则积压"
                    "只会增长",
        "rx_KL004": "被分配的消费者挂了或卡死 — 查 rebalance 日志与"
                    "成员机器",
        "rx_KL005": "回刷在消化中可接受；否则临时加消费者",
        "rpt_partitions": "积压 Top 分区",
        "col_topic": "topic[分区]",
        "col_lag": "积压",
        "col_offsets": "已提交 → 末端",
        "col_rates": "消费/生产 每秒",
        "rpt_clean": "未命中任何规则 — 消费组跟得上。",
        "rpt_disclaimer": "> 对粘贴快照的确定性规则：积压 10 万/100 万、"
                          "热点分区 5/20 倍中位数、追赶 ETA 30/180 分钟。"
                          "速率可选，缺省时相关规则静默。不连 broker。",
        "rpt_llm_note": "运维通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(KL_I18N)
