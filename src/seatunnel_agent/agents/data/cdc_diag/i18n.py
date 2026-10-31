"""EN/ZH strings for the CDC-diagnosis reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

CD_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "CDC Sync Diagnosis",
        "rpt_scope": "sections seen: {sections} · **{n}** finding(s)",
        "rpt_findings": "Findings (worst first)",
        "col_code": "code",
        "col_sev": "severity",
        "col_detail": "evidence",
        "col_rx": "prescription",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "CD001": "binlog files behind — consumer at {consumer_file}, "
                 "source at {source_file} ({files_behind} file(s))",
        "CD002": "byte lag inside {file} — {byte_lag} bytes behind",
        "CD003": "event stall — nothing consumed for {stale_s}s (last "
                 "event {last_event_ts})",
        "CD004": "retention risk — {behind_h}h behind of a "
                 "{retention_h:g}h binlog window ({share_pct}%): data "
                 "loss when the window closes",
        "CD005": "errors — {count}, classes: {classes}",
        "CD006": "consumer AHEAD of source — consumer {consumer} vs "
                 "source {source}: broken resume point",
        "rx_CD001": "check consumer throughput and whether a big "
                    "transaction or DDL wedged it; scale before the "
                    "window closes",
        "rx_CD002": "normal under load if shrinking — alert only when "
                    "it grows across snapshots",
        "rx_CD003": "the connector is wedged: check its process, the "
                    "replication user and server_id conflicts",
        "rx_CD004": "extend binlog retention NOW, then catch up — "
                    "otherwise resync from a fresh snapshot",
        "rx_CD005": "schema changes need the DDL replayed on the sink "
                    "first; duplicate keys point at a replayed resume",
        "rx_CD006": "stop the connector and reset the resume point to "
                    "the source's coordinates — continuing risks silent "
                    "gaps or duplicates",
        "rpt_clean": "No rule fired — the sync looks healthy.",
        "rpt_disclaimer": "> Deterministic rules over the pasted "
                          "snapshot: files behind 1/3, byte lag "
                          "10/200MB, stall 5/30min, retention share "
                          "50/80%. Every section is optional. No "
                          "database connection.",
        "rpt_llm_note": "Incident note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "CDC 同步异常诊断",
        "rpt_scope": "快照包含：{sections} · **{n}** 条发现",
        "rpt_findings": "发现（严重在前）",
        "col_code": "编码",
        "col_sev": "级别",
        "col_detail": "证据",
        "col_rx": "处方",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "CD001": "binlog 文件落后 — 消费端在 {consumer_file}，源端在 "
                 "{source_file}（落后 {files_behind} 个文件）",
        "CD002": "同文件内字节落后 — {file} 内落后 {byte_lag} 字节",
        "CD003": "事件停滞 — {stale_s}s 没有消费到新事件（最后事件 "
                 "{last_event_ts}）",
        "CD004": "保留期风险 — 落后 {behind_h}h，binlog 窗口 "
                 "{retention_h:g}h（占 {share_pct}%）：窗口关闭即丢数",
        "CD005": "错误 — {count} 条，分类：{classes}",
        "CD006": "消费端超前源端 — 消费端 {consumer} vs 源端 {source}："
                 "断点错乱",
        "rx_CD001": "查消费吞吐与是否被大事务/DDL 卡住；在窗口关闭前"
                    "扩容",
        "rx_CD002": "有负载时正常，持续增长才告警 — 对比多次快照",
        "rx_CD003": "连接器卡死：查进程、复制账号与 server_id 冲突",
        "rx_CD004": "立刻延长 binlog 保留期再追赶 — 否则只能重新全量",
        "rx_CD005": "schema 变更需先在目标端重放 DDL；主键冲突指向断点"
                    "重放",
        "rx_CD006": "停掉连接器，把断点重置到源端坐标 — 继续跑会悄悄"
                    "丢数或重复",
        "rpt_clean": "未命中任何规则 — 同步看起来健康。",
        "rpt_disclaimer": "> 对粘贴快照的确定性规则：文件落后 1/3、字节"
                          "落后 10/200MB、停滞 5/30 分钟、保留期占比 "
                          "50/80%。各节均可选。不连库。",
        "rpt_llm_note": "事故通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(CD_I18N)
