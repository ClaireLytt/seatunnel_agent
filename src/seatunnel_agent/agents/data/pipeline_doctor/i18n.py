"""EN/ZH strings for pipeline diagnosis reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

PD_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Pipeline Failure Diagnosis",
        "rpt_root": "target",
        "rpt_engines": "engines detected",
        "rpt_engine_unknown": "not identified",
        "rpt_stats": ("files {files} · lines {lines} · events {events} · "
                      "findings {findings} (critical {critical} / error "
                      "{error} / warn {warn}) · unmatched {unmatched}"),
        "rpt_clean": ("No known failure signature matched and no ERROR "
                      "events were found — the run looks healthy."),
        "rpt_primary": "Primary suspect",
        "rpt_findings": "Findings",
        "rpt_cause": "likely cause",
        "rpt_fix": "fix",
        "rpt_patch": "fix patch (copy-paste, adjust values)",
        "rpt_evidence": "evidence",
        "rpt_count": "occurrences",
        "rpt_files": "files",
        "rpt_first": "first seen",
        "rpt_unmatched": "Unmatched error clusters",
        "rpt_unmatched_hint": ("No knowledge-base signature matched these; "
                               "read the samples or run the LLM advice."),
        "rpt_warnings": "Warnings",
        "rpt_disclaimer": ("> Deterministic diagnosis — findings come from a "
                           "fixed failure-signature knowledge base matched "
                           "against the extracted exception clusters; the "
                           "primary suspect is the highest-severity, "
                           "earliest finding."),
    },
    "zh": {
        "rpt_title": "Pipeline 故障诊断",
        "rpt_root": "诊断目标",
        "rpt_engines": "识别到的引擎",
        "rpt_engine_unknown": "未识别",
        "rpt_stats": ("文件 {files} · 行 {lines} · 事件 {events} · "
                      "命中 {findings} (critical {critical} / error "
                      "{error} / warn {warn}) · 未命中 {unmatched}"),
        "rpt_clean": "未命中任何已知故障签名，也没有 ERROR 事件 — 本次运行看起来正常。",
        "rpt_primary": "首要嫌疑",
        "rpt_findings": "命中的故障签名",
        "rpt_cause": "可能原因",
        "rpt_fix": "修复方案",
        "rpt_patch": "修复补丁（复制即用，按需调参）",
        "rpt_evidence": "证据样本",
        "rpt_count": "出现次数",
        "rpt_files": "涉及文件",
        "rpt_first": "首次出现",
        "rpt_unmatched": "未命中的 ERROR 簇",
        "rpt_unmatched_hint": "知识库未覆盖这些异常；请查看样本，或使用 LLM 建议辅助定位。",
        "rpt_warnings": "警告",
        "rpt_disclaimer": ("> 确定性诊断 — 结论来自固定故障签名知识库与异常簇的匹配；"
                           "首要嫌疑取严重度最高、出现最早的命中项。"),
    },
}


tp = make_lookup(PD_I18N)
