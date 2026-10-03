# -*- coding: utf-8 -*-
"""Bilingual changelog rendering + optional LLM polish (advisory)."""

from __future__ import annotations

from typing import Any, Callable

from .core import GROUPS, ReleaseNotes


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


_ZH_LABELS = {key: zh for key, _en, zh in GROUPS}

_I18N = {
    "en": {
        "title": "## Release Notes",
        "version_line": ("Suggested version: **{next}** ({bump} bump"
                         "{from_part}) · {n} commits"),
        "from_part": " from {current}",
        "breaking": "### ⚠️ Breaking Changes",
        "empty": "No commits in range.",
        "polish_failed": ("> ⚠️ LLM polish failed ({err}) — showing the "
                          "deterministic changelog."),
    },
    "zh": {
        "title": "## 发布说明",
        "version_line": ("建议版本:**{next}**({bump} 级别"
                         "{from_part})· 共 {n} 个提交"),
        "from_part": ",当前 {current}",
        "breaking": "### ⚠️ 破坏性变更",
        "empty": "区间内没有提交。",
        "polish_failed": ("> ⚠️ LLM 润色失败({err})— 以下为确定性生成"
                          "的 changelog。"),
    },
}

_POLISH_SYSTEM = (
    "You are a release manager. Rewrite the given changelog for end users: "
    "merge related items, drop noise (chore/test details), keep the exact "
    "section structure and version line, keep commit hashes. Reply with "
    "markdown only, same language as the input.")


def render_markdown(notes: ReleaseNotes, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    t = _I18N[lang]
    lines = [t["title"], ""]
    if not notes.commits:
        lines.append(t["empty"])
        return "\n".join(lines)
    from_part = (t["from_part"].format(current=notes.current_version)
                 if notes.current_version else "")
    lines.append(t["version_line"].format(
        next=notes.next_version, bump=notes.bump, from_part=from_part,
        n=len(notes.commits)))
    if notes.breaking:
        lines += ["", t["breaking"]]
        for c in notes.breaking:
            sha = f" (`{c.sha}`)" if c.sha else ""
            lines.append(f"- {c.subject}{sha}")
    for key, en_label, commits in notes.grouped():
        label = _ZH_LABELS[key] if lang == "zh" else en_label
        lines += ["", f"### {label}"]
        for c in commits:
            scope = f"**{c.scope}**: " if c.scope else ""
            sha = f" (`{c.sha}`)" if c.sha else ""
            lines.append(f"- {scope}{c.subject}{sha}")
    return "\n".join(lines)


def polish_markdown(markdown: str, lang: str = "zh",
                    client_factory: Callable | None = None) -> str:
    """One advisory LLM pass over the rendered changelog; any failure
    returns the deterministic version with a warning line."""
    lang = normalize_lang(lang)
    try:
        if client_factory is None:
            from ..config import load_settings
            from ..llm import LLMClient
            client = LLMClient(load_settings(), agent="release_notes")
        else:
            client = client_factory(None)
        resp = client.chat(_POLISH_SYSTEM,
                           [{"role": "user", "content": markdown}])
        polished = (resp.reply_text or "").strip()
        return polished or markdown
    except Exception as exc:  # noqa: BLE001 — polish is advisory
        warn = _I18N[lang]["polish_failed"].format(
            err=f"{type(exc).__name__}: {exc}")
        return f"{warn}\n\n{markdown}"


def notes_to_dict(notes: ReleaseNotes) -> dict[str, Any]:
    return notes.to_dict()
