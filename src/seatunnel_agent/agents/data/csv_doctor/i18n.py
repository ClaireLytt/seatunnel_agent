"""EN/ZH strings for the CSV-doctor reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

CD_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "CSV Doctor",
        "rpt_scope": "delimiter `{delim}` · **{rows}** row(s) × "
                     "**{cols}** column(s) after repair · ● {high} / "
                     "◐ {medium} / ○ {low}",
        "rpt_clean": "The file is healthy — nothing to repair.",
        "rpt_findings": "Diagnosis",
        "col_sev": "sev",
        "col_code": "code",
        "col_count": "count",
        "col_detail": "detail",
        "CD001": "UTF-8 BOM at the start (stripped)",
        "CD002": "ragged rows vs the modal width (short rows padded, "
                 "overflow merged into the last field): {detail}",
        "CD003": "unbalanced quotes: {detail}",
        "CD004": "U+FFFD replacement characters — those bytes are "
                 "already lost upstream, re-export the file",
        "CD005": "double-encoded text repaired: {detail}",
        "CD006": "control characters stripped",
        "CD007": "duplicate header name(s) suffixed: {detail}",
        "rpt_fixed": "Repaired CSV (feeds every rows-eating agent here)",
        "rpt_disclaimer": "> Deterministic byte-level forensics plus "
                          "structural repair — the output above "
                          "round-trips through the family's CSV parser. "
                          "U+FFFD losses cannot be repaired here; fix "
                          "the exporting side's encoding.",
        "rpt_llm_note": "Incident note (LLM — review before sending)",
    },
    "zh": {
        "rpt_title": "CSV 急救",
        "rpt_scope": "分隔符 `{delim}` · 修复后 **{rows}** 行 × "
                     "**{cols}** 列 · ● {high} / ◐ {medium} / ○ {low}",
        "rpt_clean": "文件健康 — 无需修复。",
        "rpt_findings": "诊断",
        "col_sev": "级",
        "col_code": "编码",
        "col_count": "数量",
        "col_detail": "明细",
        "CD001": "文件头 UTF-8 BOM（已剥除）",
        "CD002": "列数漂移行（短行补空,溢出并入末列）: {detail}",
        "CD003": "引号不配对: {detail}",
        "CD004": "U+FFFD 替换符 — 字节已在上游丢失,无法恢复,需重新导出",
        "CD005": "双重编码乱码已复原: {detail}",
        "CD006": "控制字符已剥除",
        "CD007": "表头重名已加后缀: {detail}",
        "rpt_fixed": "修复后 CSV（可直接喂给本工作台所有吃行数据的 agent）",
        "rpt_disclaimer": "> 确定性字节取证 + 结构修复 — 上面的产出已经"
                          "通过本仓 CSV 解析器回检。U+FFFD 的丢失在这里"
                          "救不回来,要修导出侧的编码。",
        "rpt_llm_note": "事故说明（LLM — 发送前请复核）",
    },
}

tp = make_lookup(CD_I18N)
