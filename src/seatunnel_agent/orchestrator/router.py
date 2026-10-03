# -*- coding: utf-8 -*-
"""No-API-key fallback: deterministic keyword routing.

When no LLM is configured the chat entry cannot orchestrate, but it can
still tell the user which agent (and Web UI page) fits their request —
suggest only, never execute.
"""

from __future__ import annotations

from dataclasses import dataclass

from .catalog import AgentSpec

# keyword → tool name, scored by hit count (zh + en keywords per tool)
_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sql_review": ("审查", "review", "代码检查", "cr", "质量", "规范",
                   "性能问题"),
    "sql_transpile": ("翻译", "方言", "transpile", "translate", "doris",
                      "starrocks", "转成", "转换"),
    "impact_diff": ("影响", "impact", "变更", "blast", "上线", "diff"),
    "migrate_to_seatunnel": ("datax", "sqoop", "迁移", "migrate"),
    "skew_check": ("倾斜", "skew", "数据倾斜"),
    "sql_fmt": ("格式化", "format", "排版", "美化"),
    "config_lint": ("配置", "hocon", "conf", "lint", "连接器", "connector"),
    "schema_drift": ("漂移", "drift", "ddl", "表结构变更", "schema"),
    "pii_scan": ("敏感", "pii", "脱敏", "手机号", "身份证"),
    "sql_testgen": ("造数", "测试数据", "test data", "testgen", "mock"),
    "secret_scan": ("凭证", "密钥", "泄漏", "secret", "secrets", "leak",
                    "leaked", "credential", "credentials", "token",
                    "api key", "泄密", "密码检查"),
    "dep_check": ("依赖", "dependency", "requirements", "license", "版本钉"),
    "release_notes": ("发布", "changelog", "release", "版本号", "release notes"),
    "ci_triage": ("ci", "流水线", "构建失败", "actions", "flaky", "作业日志"),
}


@dataclass
class Suggestion:
    tool: str
    description: str
    page: str
    score: int


def _hit(word: str, text: str) -> bool:
    """ASCII keywords match on word boundaries ("cr" must not fire inside
    "create"/"script"); CJK keywords match as substrings (no spaces in zh)."""
    import re
    if re.fullmatch(r"[a-z0-9 ]+", word):
        return re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])",
                         text) is not None
    return word in text


def suggest(request: str, catalog: dict[str, AgentSpec],
            top: int = 3) -> list[Suggestion]:
    """Top-N agents whose keywords appear in *request* (case-insensitive)."""
    text = (request or "").lower()
    scored: list[Suggestion] = []
    for tool, words in _KEYWORDS.items():
        spec = catalog.get(tool)
        if spec is None:
            continue
        score = sum(1 for w in words if _hit(w, text))
        if score:
            scored.append(Suggestion(tool=tool, description=spec.description,
                                     page=spec.page, score=score))
    scored.sort(key=lambda s: -s.score)
    return scored[:top]


def render_suggestions(suggestions: list[Suggestion],
                       lang: str = "zh") -> str:
    zh = not (lang or "").lower().startswith("en")
    if not suggestions:
        return ("未配置 LLM,且没有匹配到合适的 agent —— 可在 /settings 配置"
                " API key 后使用智能编排。" if zh else
                "No LLM configured and no agent matched — configure an API "
                "key on /settings to use the orchestrator.")
    head = ("未配置 LLM,无法智能编排;根据关键词推荐以下 agent:" if zh else
            "No LLM configured — based on keywords, try these agents:")
    lines = [head, ""]
    for s in suggestions:
        page = f" → `{s.page}`" if s.page else ""
        lines.append(f"- **{s.tool}**{page}: {s.description[:120]}")
    return "\n".join(lines)
