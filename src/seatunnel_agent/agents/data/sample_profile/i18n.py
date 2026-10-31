"""EN/ZH strings for the sample-profile reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

SAMPLE_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Sample Profile",
        "rpt_scope": "profiled **{sampled}** of **{total}** rows "
                     "(deterministic stride sample) · {cols} columns",
        "rpt_columns": "Column profiles",
        "col_name": "column",
        "col_kind": "kind",
        "col_null": "null%",
        "col_unique": "unique%",
        "col_range": "range / top values",
        "rpt_findings": "Findings ({n})",
        "rpt_no_findings": "No anomaly fired — the sample looks clean.",
        "col_code": "code",
        "col_sev": "severity",
        "col_col": "column",
        "col_detail": "evidence",
        "sev_high": "high",
        "sev_mid": "mid",
        "sev_low": "low",
        "SP001": "mixed types — no format reaches 90% ({buckets}); "
                 "the column holds more than one kind of value",
        "SP002": "high null rate — {null_pct}% of rows are empty",
        "SP003": "constant / empty column — carries no information "
                 "({detail})",
        "SP004": "outlier format — dominant '{dominant}' with stragglers "
                 "{minority}; e.g. {examples}",
        "SP005": "numeric stored as text — grouping or currency noise "
                 "like {examples}",
        "SP006": "whitespace / case drift — the same value appears as "
                 "{variants}",
        "rpt_disclaimer": "> Deterministic profile over the submitted "
                          "sample; percentages refer to the sampled rows. "
                          "No database connection.",
        "rpt_llm_note": "Data-review note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "数据抽样剖析",
        "rpt_scope": "剖析 **{sampled}** / **{total}** 行"
                     "（确定性等距抽样）· {cols} 列",
        "rpt_columns": "列剖面",
        "col_name": "列",
        "col_kind": "类型",
        "col_null": "空值%",
        "col_unique": "唯一%",
        "col_range": "范围 / 高频值",
        "rpt_findings": "发现（{n} 条）",
        "rpt_no_findings": "未命中任何异常规则 — 样本看起来干净。",
        "col_code": "编码",
        "col_sev": "级别",
        "col_col": "列",
        "col_detail": "证据",
        "sev_high": "高",
        "sev_mid": "中",
        "sev_low": "低",
        "SP001": "混合类型 — 无一种格式达到 90%（{buckets}），"
                 "该列装了不止一种值",
        "SP002": "高空值率 — {null_pct}% 的行为空",
        "SP003": "常量/全空列 — 不携带信息（{detail}）",
        "SP004": "离群格式 — 主格式 '{dominant}'，掉队者 {minority}；"
                 "如 {examples}",
        "SP005": "数值被存成文本 — 含千分位/货币符等噪音，如 {examples}",
        "SP006": "空白/大小写漂移 — 同一个值写成 {variants}",
        "rpt_disclaimer": "> 对提交样本的确定性剖析；百分比以抽样行为分母。"
                          "不连数据库。",
        "rpt_llm_note": "数据体检通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(SAMPLE_I18N)
