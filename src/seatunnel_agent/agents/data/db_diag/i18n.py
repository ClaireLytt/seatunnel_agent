"""EN/ZH strings for the db-diagnosis reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

DB_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Database Runtime Diagnosis",
        "rpt_scope": "sections seen: {sections} · **{n}** finding(s)",
        "rpt_findings": "Findings (worst first)",
        "col_code": "code",
        "col_sev": "severity",
        "col_detail": "evidence",
        "col_rx": "prescription",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "DB001": "connection pool pressure — {threads_connected}/"
                 "{max_connections} ({used_pct}%)",
        "DB002": "running-thread storm — {threads_running} threads "
                 "executing at once",
        "DB003": "long lock waits — {count} wait(s), worst "
                 "{worst_seconds:g}s: {top}",
        "DB004": "deadlocks detected — {count} in the snapshot window",
        "DB005": "slow-query hotspots — {count} over 1s, top: {top}",
        "DB006": "CPU saturation — {cpu_pct:g}%",
        "rx_DB001": "raise max_connections cautiously or add pooling; "
                    "hunt idle connections first",
        "rx_DB002": "find the common blocker (locks or a hot slow query) "
                    "before adding capacity",
        "rx_DB003": "kill or commit the blocking transaction; shorten "
                    "transactions touching that table",
        "rx_DB004": "fetch SHOW ENGINE INNODB STATUS and fix the lock "
                    "ordering of the two statements",
        "rx_DB005": "run the slow-query RCA (`seatunnel-agent "
                    "slowquery`) and the index advisor "
                    "(`seatunnel-agent index-adv`)",
        "rx_DB006": "correlate with DB002/DB005 — CPU rarely saturates "
                    "alone",
        "rpt_clean": "No rule fired — the snapshot looks healthy.",
        "rpt_disclaimer": "> Deterministic rules over the pasted "
                          "snapshot: pool at 80/95%, running threads "
                          "32/128, lock waits 5/30s, slow queries over "
                          "1s, CPU 80/95%. No live connection.",
        "rpt_llm_note": "Incident note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "数据库运行诊断",
        "rpt_scope": "快照包含：{sections} · **{n}** 条发现",
        "rpt_findings": "发现（严重在前）",
        "col_code": "编码",
        "col_sev": "级别",
        "col_detail": "证据",
        "col_rx": "处方",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "DB001": "连接池吃紧 — {threads_connected}/{max_connections}"
                 "（{used_pct}%）",
        "DB002": "执行线程风暴 — 同时执行 {threads_running} 个线程",
        "DB003": "长锁等待 — {count} 个，最长 {worst_seconds:g}s：{top}",
        "DB004": "检出死锁 — 快照窗口内 {count} 次",
        "DB005": "慢查询热点 — {count} 条超 1s，最慢：{top}",
        "DB006": "CPU 饱和 — {cpu_pct:g}%",
        "rx_DB001": "谨慎上调 max_connections 或加连接池；先清理空闲连接",
        "rx_DB002": "先找共同阻塞点（锁或热点慢查询），再谈扩容",
        "rx_DB003": "杀掉或提交阻塞事务；缩短碰该表的事务",
        "rx_DB004": "取 SHOW ENGINE INNODB STATUS，修正两条语句的加锁顺序",
        "rx_DB005": "跑慢查询根因（`seatunnel-agent slowquery`）与索引"
                    "推荐（`seatunnel-agent index-adv`）",
        "rx_DB006": "与 DB002/DB005 关联看 — CPU 很少单独饱和",
        "rpt_clean": "未命中任何规则 — 快照看起来健康。",
        "rpt_disclaimer": "> 对粘贴快照的确定性规则：连接池 80/95%、执行"
                          "线程 32/128、锁等待 5/30s、慢查询 >1s、CPU "
                          "80/95%。不连库。",
        "rpt_llm_note": "事故通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(DB_I18N)
