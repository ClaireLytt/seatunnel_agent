"""No-API-key fallback: deterministic keyword routing.

When no LLM is configured the chat entry cannot orchestrate, but it can
still tell the user which agent (and Web UI page) fits their request —
suggest only, never execute.
"""

from __future__ import annotations

from dataclasses import dataclass

from seatunnel_agent.common.utils import normalize_lang

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
    "skew_drift": ("倾斜漂移", "漂移", "分片键", "splitkey", "split key",
                   "基线", "热点值", "hot value"),
    "skew_runtime_history": ("拖尾", "straggler", "history server",
                             "运行时倾斜", "spark 任务"),
    "skew_runtime_flink": ("flink",),
    "sql_fmt": ("格式化", "format", "排版", "美化"),
    "config_lint": ("配置", "hocon", "conf", "lint", "连接器", "connector"),
    "schema_drift": ("漂移", "drift", "ddl", "表结构变更", "schema"),
    "sql_testgen": ("造数", "测试数据", "test data", "testgen", "mock"),
    "secret_scan": ("凭证", "密钥", "泄漏", "secret", "secrets", "leak",
                    "leaked", "credential", "credentials", "token",
                    "api key", "泄密", "密码检查"),
    "dep_check": ("依赖", "dependency", "requirements", "license", "版本钉"),
    "release_notes": ("发布", "changelog", "release", "版本号", "release notes"),
    "ci_triage": ("ci", "流水线", "构建失败", "actions", "flaky", "作业日志"),
}


# English one-liners for the keyword-routable tools: catalog descriptions
# come from (Chinese) docstrings, so the EN fallback needs its own copy.
_DESCRIPTIONS_EN: dict[str, str] = {
    "sql_review": ("Static SQL review — performance/quality/standards rules, "
                   "severity-graded Markdown report."),
    "sql_transpile": ("SQL dialect translation (hive/spark/doris/starrocks …) "
                      "with an incompatibility report — deterministic."),
    "impact_diff": ("Change-impact analysis — diff two SQL versions and report "
                    "the downstream blast radius with severity levels."),
    "migrate_to_seatunnel": ("Convert a DataX job JSON or sqoop command into a "
                             "SeaTunnel config with migration notes."),
    "skew_check": ("Static data-skew scan over SQL — join/aggregation skew "
                   "patterns with rewrite suggestions."),
    "skew_drift": ("Skew drift check — the latest split-key measurement vs "
                   "its historical baseline, with hot-value identity."),
    "skew_runtime_history": ("Runtime skew diagnosis from Spark History "
                             "Server task metrics — straggler stages."),
    "skew_runtime_flink": ("Runtime skew diagnosis from Flink REST "
                           "per-subtask metrics (SeaTunnel on Flink)."),
    "sql_fmt": ("Deterministic SQL pretty-print — statements that do not "
                "parse are kept verbatim."),
    "config_lint": ("Param-level lint of SeaTunnel configs against the "
                    "built-in connector docs, with did-you-mean hints."),
    "schema_drift": ("Diff two DDL snapshots — breaking / risk / info severity "
                     "for every structural change."),
    "sql_testgen": ("Generate join-aware test datasets that exercise a query, "
                    "validated on in-memory SQLite."),
    "secret_scan": ("Scan text for leaked credentials — provider tokens, "
                    "private keys, password assignments; previews masked."),
    "dep_check": ("Dependency health — declared vs installed, unpinned specs, "
                  "duplicate pins and a license inventory, offline."),
    "release_notes": ("Grouped changelog from conventional commits plus a "
                      "semver bump suggestion."),
    "ci_triage": ("Cluster failed CI job logs into root causes; spot flaky "
                  "jobs and duration drift."),
}


# manifest-declared tools (governance agents) contribute their own routing
# keywords and EN descriptions
def _merge_manifest_tools() -> None:
    from seatunnel_agent.hub.registry import discover_tools

    for tm in discover_tools():
        _KEYWORDS.setdefault(tm.name, tm.keywords)
        _DESCRIPTIONS_EN.setdefault(tm.name, tm.router_en)


_merge_manifest_tools()


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
    zh = normalize_lang(lang) == "zh"
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
        desc = (s.description if zh
                else _DESCRIPTIONS_EN.get(s.tool, s.description))
        lines.append(f"- **{s.tool}**{page}: {desc[:120]}")
    return "\n".join(lines)
