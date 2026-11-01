"""EN/ZH strings for the duplicate-check reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

DUP_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Duplicate Check",
        "rpt_scope": "**{total}** rows · extra duplicate rows: full-row "
                     "**{row}**, primary-key **{pk}**, business-key "
                     "**{biz}**",
        "rpt_keys": "keys — primary: {pk}; business: {biz}; (none) means "
                    "the layer was skipped",
        "rpt_groups": "Duplicate groups (top {n})",
        "col_layer": "layer",
        "col_key": "key value",
        "col_count": "rows",
        "col_span": "first → last row",
        "col_diff": "differing columns",
        "layer_row": "full-row",
        "layer_pk": "primary-key",
        "layer_biz": "business-key",
        "rpt_clean": "No duplicate fired — every checked layer is unique.",
        "rpt_hint_row": "> full-row duplicates usually mean a retried load "
                        "or a doubled upstream partition — dedup at the "
                        "sink or make the load idempotent.",
        "rpt_hint_keys": "> key duplicates whose differing columns are "
                         "timestamps/amounts point at missing dedup "
                         "windows; differing source columns point at "
                         "upstream fan-out.",
        "rpt_disclaimer": "> Deterministic scan of the submitted rows; "
                          "rows with a null key are skipped in key "
                          "layers. No database connection.",
        "rpt_llm_note": "Dedup note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "数据重复检测",
        "rpt_scope": "**{total}** 行 · 多余重复行：全行 **{row}**、"
                     "主键 **{pk}**、业务键 **{biz}**",
        "rpt_keys": "键 — 主键: {pk}；业务键: {biz}；(none) 表示该层未检",
        "rpt_groups": "重复组（前 {n} 组）",
        "col_layer": "层",
        "col_key": "键值",
        "col_count": "行数",
        "col_span": "首行 → 末行",
        "col_diff": "差异列",
        "layer_row": "全行",
        "layer_pk": "主键",
        "layer_biz": "业务键",
        "rpt_clean": "未发现重复 — 已检各层均唯一。",
        "rpt_hint_row": "> 全行重复通常来自重跑/重复加载或上游分区翻倍 — "
                        "在 sink 去重或把加载改成幂等。",
        "rpt_hint_keys": "> 键重复的差异列若是时间戳/金额，指向缺少去重"
                         "窗口；差异列若是来源字段，指向上游多路写入。",
        "rpt_disclaimer": "> 对提交数据行的确定性扫描；键层跳过键为空的行。"
                          "不连数据库。",
        "rpt_llm_note": "去重处置通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(DUP_I18N)
