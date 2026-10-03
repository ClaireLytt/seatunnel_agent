# -*- coding: utf-8 -*-
"""Bilingual markdown report for CI triage."""

from __future__ import annotations

from .core import CiReport


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


_I18N = {
    "en": {
        "title": "## CI Log Triage",
        "log_stats": ("logs {logs} · error events {events} · root-cause "
                      "clusters **{clusters}**"),
        "cluster_header": "Count | Jobs | Root-cause template",
        "no_clusters": "✅ No error events found in the logs.",
        "flaky_title": "### 🎲 Flaky (same commit, both pass & fail)",
        "flaky_line": "- `{workflow}` @ `{sha}`",
        "drift_title": "### 🐢 Duration drift",
        "drift_line": ("- `{workflow}`: latest {latest}s vs median {median}s "
                       "(×{factor})"),
        "wf_title": "### Workflows",
        "wf_header": "Workflow | Runs | Failures | Fail rate",
        "sample": "sample",
    },
    "zh": {
        "title": "## CI 日志诊断",
        "log_stats": ("日志 {logs} 份 · 错误事件 {events} · 根因聚类 "
                      "**{clusters}** 个"),
        "cluster_header": "次数 | 作业 | 根因模板",
        "no_clusters": "✅ 日志中没有发现错误事件。",
        "flaky_title": "### 🎲 Flaky(同一提交又过又挂)",
        "flaky_line": "- `{workflow}` @ `{sha}`",
        "drift_title": "### 🐢 时长漂移",
        "drift_line": ("- `{workflow}`:最新 {latest}s,历史中位数 "
                       "{median}s(×{factor})"),
        "wf_title": "### 工作流概览",
        "wf_header": "工作流 | 运行 | 失败 | 失败率",
        "sample": "样例",
    },
}


def _esc(text: str) -> str:
    return text.replace("|", "\\|").replace("`", "'")


def render_markdown(report: CiReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    t = _I18N[lang]
    lines = [t["title"], ""]
    if report.logs_analyzed:
        lines.append(t["log_stats"].format(
            logs=report.logs_analyzed, events=report.error_events,
            clusters=len(report.clusters)))
        if report.clusters:
            lines += ["", "| " + t["cluster_header"] + " |", "|---|---|---|"]
            for c in report.clusters:
                jobs = ", ".join(f"`{j}`" for j in sorted(c.jobs))
                lines.append(f"| {c.count} | {jobs} | {_esc(c.template)} |")
            first = report.clusters[0]
            lines += ["", f"> {t['sample']}: `{_esc(first.sample)[:160]}`"]
        else:
            lines += ["", t["no_clusters"]]
    if report.runs.flaky:
        lines += ["", t["flaky_title"]]
        for f in report.runs.flaky:
            lines.append(t["flaky_line"].format(workflow=f["workflow"],
                                                sha=f["head_sha"]))
    if report.runs.drift:
        lines += ["", t["drift_title"]]
        for d in report.runs.drift:
            lines.append(t["drift_line"].format(
                workflow=d["workflow"], latest=d["latest_s"],
                median=d["median_s"], factor=d["factor"]))
    if report.runs.workflows:
        lines += ["", t["wf_title"], "",
                  "| " + t["wf_header"] + " |", "|---|---|---|---|"]
        for w in report.runs.workflows:
            lines.append(f"| `{w['workflow']}` | {w['runs']} "
                         f"| {w['failures']} | {w['fail_rate']:.0%} |")
    return "\n".join(lines)
