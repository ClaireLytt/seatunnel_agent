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
        "diff_title": "Run Regression Diff",
        "diff_roots": "current `{cur}` vs baseline `{base}`",
        "diff_stats": ("appeared {appeared} · gone {gone} · grew {grew} · "
                       "KB hits {findings}"),
        "diff_clean": ("No new or grown exception clusters vs the baseline "
                       "— the failure is not visible in these logs, or both "
                       "runs share it."),
        "diff_appeared": "New clusters (regression candidates)",
        "diff_grew": "Grown clusters",
        "diff_grew_note": "count {now} (baseline {base})",
        "diff_gone": "Clusters gone since the baseline",
        "diff_findings": "KB diagnosis of the new/grown clusters",
        "diff_disclaimer": ("> Deterministic diff — clusters are keyed by "
                            "root-cause signature; only clusters new or "
                            "grown vs the baseline are diagnosed."),
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
        "diff_title": "运行回归对比",
        "diff_roots": "当前 `{cur}` vs 基线 `{base}`",
        "diff_stats": "新增 {appeared} · 消失 {gone} · 增长 {grew} · 知识库命中 {findings}",
        "diff_clean": "相对基线没有新增或显著增长的异常簇 — 故障不在这些日志里，或两次运行共有。",
        "diff_appeared": "新出现的异常簇（回归嫌疑）",
        "diff_grew": "显著增长的异常簇",
        "diff_grew_note": "次数 {now}（基线 {base}）",
        "diff_gone": "相对基线消失的异常簇",
        "diff_findings": "新增/增长簇的知识库诊断",
        "diff_disclaimer": ("> 确定性对比 — 异常簇按根因签名对齐；"
                            "只诊断相对基线新增或增长的簇。"),
        "rpt_disclaimer": ("> 确定性诊断 — 结论来自固定故障签名知识库与异常簇的匹配；"
                           "首要嫌疑取严重度最高、出现最早的命中项。"),
    },
}


tp = make_lookup(PD_I18N)
