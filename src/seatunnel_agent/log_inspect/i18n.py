# -*- coding: utf-8 -*-
"""EN/ZH strings for log inspection reports and the /loginspect page."""

from __future__ import annotations

LGI_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Batch Log Inspection",
        "rpt_root": "root",
        "rpt_stats": ("files {files} · lines {lines} · events {events} · "
                      "clusters {clusters} (error {error} / warn {warn})"),
        "rpt_clean": "No ERROR/WARN events found — the logs look clean.",
        "rpt_top": "Top clusters",
        "rpt_col_level": "level",
        "rpt_col_exception": "exception / template",
        "rpt_col_count": "count",
        "rpt_col_files": "files",
        "rpt_col_first": "first seen",
        "rpt_col_last": "last seen",
        "rpt_cluster": "Cluster",
        "rpt_template": "template",
        "rpt_top_frame": "top frame",
        "rpt_files": "files",
        "rpt_sample": "sample",
        "rpt_warnings": "Warnings",
        "rpt_disclaimer": (
            "> Deterministic scan — volatile tokens (numbers, paths, "
            "addresses, ids) are masked before clustering, so counts group "
            "recurrences of the same root cause."),
    },
    "zh": {
        "rpt_title": "批量日志巡检",
        "rpt_root": "扫描目标",
        "rpt_stats": ("文件 {files} · 行 {lines} · 事件 {events} · "
                      "簇 {clusters} (error {error} / warn {warn})"),
        "rpt_clean": "未发现 ERROR/WARN 事件 — 日志看起来是干净的。",
        "rpt_top": "Top 异常簇",
        "rpt_col_level": "级别",
        "rpt_col_exception": "异常 / 模板",
        "rpt_col_count": "次数",
        "rpt_col_files": "文件数",
        "rpt_col_first": "首次出现",
        "rpt_col_last": "末次出现",
        "rpt_cluster": "簇",
        "rpt_template": "消息模板",
        "rpt_top_frame": "栈顶帧",
        "rpt_files": "涉及文件",
        "rpt_sample": "代表样本",
        "rpt_warnings": "警告",
        "rpt_disclaimer": (
            "> 确定性扫描 — 聚类前已归一化易变片段（数字/路径/地址/ID），"
            "同一根因的反复出现会归入同一簇。"),
    },
}


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


def tp(lang: str, key: str) -> str:
    lang = normalize_lang(lang)
    return LGI_I18N.get(lang, {}).get(key) or LGI_I18N["zh"].get(key, key)
