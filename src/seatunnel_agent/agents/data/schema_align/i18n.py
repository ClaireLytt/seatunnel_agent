"""EN/ZH strings for the schema-align reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

SAL_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Source-Sink Schema Alignment",
        "rpt_scope": "`{src}` → `{dst}` · **{matched}** column(s) "
                     "matched · **{n}** finding(s)",
        "rpt_findings": "Findings (worst first)",
        "col_code": "code",
        "col_sev": "severity",
        "col_column": "column",
        "col_detail": "evidence",
        "col_rx": "prescription",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "SA001": "missing in sink — `{src}` is silently dropped",
        "SA002": "extra NOT NULL in sink without default — `{dst}`: "
                 "every insert fails",
        "SA003": "narrowing — {src} → {dst} ({kind})",
        "SA004": "risky conversion — {src} → {dst}: parses at run time, "
                 "dies on the first bad row",
        "SA005": "temporal truncation — {src} → {dst}: the time of day "
                 "is lost",
        "SA006": "nullable → NOT NULL — {src} → {dst}: the first NULL "
                 "kills the batch",
        "rx_SA001": "add the column to the sink, or declare the drop in "
                    "the job's field mapping on purpose",
        "rx_SA002": "give it a DEFAULT or fill it in the transform",
        "rx_SA003": "widen the sink type — narrowing fails on real "
                    "data, not on the test rows",
        "rx_SA004": "cast in the transform with an explicit bad-row "
                    "policy, never implicitly at the sink",
        "rx_SA005": "use timestamp/datetime at the sink, or truncate "
                    "deliberately in the transform",
        "rx_SA006": "relax the sink to nullable, or COALESCE in the "
                    "transform",
        "rpt_clean": "Every matched column maps safely; widenings pass "
                     "silently.",
        "rpt_disclaimer": "> Deterministic name-matched type judgment "
                          "over the two DDLs (MySQL/Hive/Doris "
                          "spellings parse). Widenings (int→bigint, "
                          "date→timestamp, anything→string) are safe "
                          "and not reported. No database connection.",
        "rpt_llm_note": "Alignment note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "源目 Schema 对齐",
        "rpt_scope": "`{src}` → `{dst}` · 对上 **{matched}** 列 · "
                     "**{n}** 条发现",
        "rpt_findings": "发现（严重在前）",
        "col_code": "编码",
        "col_sev": "级别",
        "col_column": "列",
        "col_detail": "证据",
        "col_rx": "处方",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "SA001": "目标端缺列 — `{src}` 会被悄悄丢掉",
        "SA002": "目标端多出无默认值的 NOT NULL 列 — `{dst}`：每条写入"
                 "都会失败",
        "SA003": "类型收窄 — {src} → {dst}（{kind}）",
        "SA004": "危险转换 — {src} → {dst}：运行时才解析，第一条脏数据"
                 "就挂",
        "SA005": "时间截断 — {src} → {dst}：时分秒会丢失",
        "SA006": "可空 → NOT NULL — {src} → {dst}：第一个 NULL 就打挂"
                 "整批",
        "rx_SA001": "目标端补列,或在作业字段映射里显式声明丢弃",
        "rx_SA002": "给默认值,或在 transform 里填充",
        "rx_SA003": "放宽目标端类型 — 收窄在真实数据上才炸,测试行看"
                    "不出来",
        "rx_SA004": "在 transform 显式 cast 并配脏行策略,不要在 sink "
                    "隐式转",
        "rx_SA005": "目标端用 timestamp/datetime,或在 transform 里"
                    "有意截断",
        "rx_SA006": "目标端放宽为可空,或 transform 里 COALESCE",
        "rpt_clean": "对上的列全部安全映射;放宽类转换静默通过。",
        "rpt_disclaimer": "> 对两份 DDL 的确定性按名匹配类型判定"
                          "（MySQL/Hive/Doris 写法均可解析）;放宽"
                          "（int→bigint、date→timestamp、任意→string）"
                          "安全不报。不连数据库。",
        "rpt_llm_note": "对齐通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(SAL_I18N)
