"""EN/ZH strings for the realtime-offline reconciliation reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

RO_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Realtime vs Offline Reconciliation",
        "rpt_scope": "keys {keys} · tolerance ±{tol:g}% · realtime "
                     "**{rt}** rows vs offline **{off}** rows · matched "
                     "**{matched}** · consistent **{consistent}%**",
        "rpt_grace": " · grace on `{key}`: {values} excluded (window "
                     "may not have closed)",
        "rpt_missing": "Missing keys",
        "missing_rt": "- missing in realtime ({n}): {examples}",
        "missing_off": "- missing in offline ({n}): {examples}",
        "rpt_mismatches": "Mismatches over tolerance (worst first, "
                          "{n} total)",
        "col_key": "key",
        "col_column": "column",
        "col_rt": "realtime",
        "col_off": "offline",
        "col_diff": "diff %",
        "rpt_biases": "Systematic bias",
        "bias_rt_lower": "`{column}` — realtime consistently LOWER "
                         "(median {median_diff_pct}%, {affected} "
                         "cell(s)): late data or unclosed windows",
        "bias_rt_higher": "`{column}` — realtime consistently HIGHER "
                          "(median {median_diff_pct}%, {affected} "
                          "cell(s)): duplicate consumption or double "
                          "counting",
        "rpt_clean": "Both sides agree within tolerance — no missing "
                     "keys, no mismatches.",
        "rpt_disclaimer": "> Deterministic key-aligned comparison of the "
                          "pasted result sets; shared non-key columns "
                          "are compared numerically under the relative "
                          "tolerance. For connected checksum comparison "
                          "use the Data Comparison agent.",
        "rpt_llm_note": "Reconciliation note (LLM — review before "
                        "sending)",
    },
    "zh": {
        "rpt_title": "实时与离线核对",
        "rpt_scope": "键 {keys} · 容差 ±{tol:g}% · 实时 **{rt}** 行 vs "
                     "离线 **{off}** 行 · 对齐 **{matched}** · 一致率 "
                     "**{consistent}%**",
        "rpt_grace": " · `{key}` 宽限：排除 {values}（窗口可能未闭合）",
        "rpt_missing": "缺失键",
        "missing_rt": "- 实时侧缺失（{n}）：{examples}",
        "missing_off": "- 离线侧缺失（{n}）：{examples}",
        "rpt_mismatches": "超容差差异（差距大在前，共 {n} 处）",
        "col_key": "键",
        "col_column": "列",
        "col_rt": "实时",
        "col_off": "离线",
        "col_diff": "差异 %",
        "rpt_biases": "系统性偏差",
        "bias_rt_lower": "`{column}` — 实时普遍偏低（中位数 "
                         "{median_diff_pct}%，{affected} 处）：迟到数据"
                         "或窗口未闭合",
        "bias_rt_higher": "`{column}` — 实时普遍偏高（中位数 "
                          "{median_diff_pct}%，{affected} 处）：重复消费"
                          "或重复计数",
        "rpt_clean": "两侧在容差内一致 — 无缺失键、无超差。",
        "rpt_disclaimer": "> 对粘贴结果集的确定性按键对齐比较；共同的"
                          "非键列按相对容差做数值比较。连库 checksum "
                          "比对请用 Data Comparison agent。",
        "rpt_llm_note": "核对通报草稿（LLM — 发送前请复核）",
    },
}

tp = make_lookup(RO_I18N)
