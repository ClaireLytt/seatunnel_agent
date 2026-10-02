# -*- coding: utf-8 -*-
"""EN/ZH strings for config lint reports and the /conflint page."""

from __future__ import annotations

CFL_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "SeaTunnel Config Lint",
        "rpt_stats": ("connectors {connectors} · findings {total} "
                      "(error {error} / warn {warn} / info {info})"),
        "rpt_batch_stats": ("files {files} · pass {passed} · findings {total} "
                            "(error {error} / warn {warn} / info {info})"),
        "rpt_clean": "No findings — the config passes the deep lint.",
        "rpt_ok": "PASS",
        "rpt_fail": "FAIL",
        "rpt_disclaimer": (
            "> Deterministic lint against the built-in connector docs (19 "
            "connectors) — parsed, never executed. Undocumented connectors "
            "get name-level checks only."),
        # finding messages, keyed by kind
        "msg_syntax_error": "HOCON parse failed: {detail}",
        "msg_unresolved_subst": "unresolved ${{...}} substitution: {detail}",
        "msg_missing_section": "missing required section",
        "msg_empty_section": "section has no connector block",
        "msg_unknown_connector": "unknown connector{suggestion_tail}",
        "msg_role_mismatch": "this connector is {role}-only — wrong section",
        "msg_missing_required": "missing required param (e.g. {example})",
        "msg_unknown_param": "unknown param{suggestion_tail}",
        "msg_type_mismatch": "expects {declared}, got {actual}",
        "msg_enum_mismatch": "value '{value}' not in allowed: {allowed}",
        "msg_bad_job_mode": "job.mode '{value}' invalid — use {allowed}",
        "msg_cdc_requires_stream": "CDC source requires job.mode = STREAMING",
        "msg_bad_parallelism": "parallelism must be a positive int, got {value}",
        "sugg_tail": " — did you mean `{s}`?",
    },
    "zh": {
        "rpt_title": "SeaTunnel 配置深度检查",
        "rpt_stats": ("连接器 {connectors} · 发现 {total} "
                      "(错误 {error} / 警告 {warn} / 提示 {info})"),
        "rpt_batch_stats": ("文件 {files} · 通过 {passed} · 发现 {total} "
                            "(错误 {error} / 警告 {warn} / 提示 {info})"),
        "rpt_clean": "未发现问题 — 配置通过深度检查。",
        "rpt_ok": "通过",
        "rpt_fail": "未通过",
        "rpt_disclaimer": (
            "> 基于内置连接器文档（19 个连接器）的确定性检查 — 只解析不执行。"
            "未收录的连接器仅做名称级检查。"),
        "msg_syntax_error": "HOCON 解析失败: {detail}",
        "msg_unresolved_subst": "存在无法解析的 ${{...}} 占位符: {detail}",
        "msg_missing_section": "缺少必需的配置段",
        "msg_empty_section": "配置段内没有连接器",
        "msg_unknown_connector": "未知连接器{suggestion_tail}",
        "msg_role_mismatch": "该连接器只能用于 {role} — 用错了配置段",
        "msg_missing_required": "缺少必填参数（示例: {example}）",
        "msg_unknown_param": "未知参数{suggestion_tail}",
        "msg_type_mismatch": "类型应为 {declared}，实际是 {actual}",
        "msg_enum_mismatch": "取值 '{value}' 不在允许范围: {allowed}",
        "msg_bad_job_mode": "job.mode '{value}' 非法 — 应为 {allowed}",
        "msg_cdc_requires_stream": "CDC 源要求 job.mode = STREAMING",
        "msg_bad_parallelism": "parallelism 必须是正整数，实际是 {value}",
        "sugg_tail": " — 是不是想写 `{s}`？",
    },
}


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


def tp(lang: str, key: str) -> str:
    lang = normalize_lang(lang)
    return CFL_I18N.get(lang, {}).get(key) or CFL_I18N["zh"].get(key, key)


def finding_message(lang: str, kind: str, params: dict[str, str]) -> str:
    tmpl = tp(lang, f"msg_{kind}")
    fmt = dict(params)
    suggestion = fmt.pop("suggestion", "")
    fmt["suggestion_tail"] = (
        tp(lang, "sugg_tail").format(s=suggestion) if suggestion else "")
    try:
        return tmpl.format(**fmt)
    except (KeyError, IndexError):
        return tmpl
