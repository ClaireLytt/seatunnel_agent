"""i18n parity for the React /seatunnel workspace (ticket 07).

Checks frontend/seatunnel/src/i18n.ts:

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the legacy Gradio page carry its wording verbatim.

The legacy expected values live INLINE below: this test is now the parity
source of truth. The legacy page's UI-chrome i18n keys were pruned from
seatunnel.rendering.I18N on retirement (react_migration.md item 6 — the
backend keeps only the keys it renders itself), so the wording here was
copied verbatim from `git show 5b42cf0:src/.../seatunnel/ui.py` (_I18N
dict, plus the f-strings noted per key).

Keys with no legacy wording to check (new aria/UI text on the React page):
- upload: the legacy UploadButton was a bare "+" glyph (ui.py:997) — the
  React button keeps the "+" glyph and adds an aria-label.
- collapseSidebar/expandSidebar: legacy toggles were bare "☰" glyphs
  (ui.py:936/983); React uses «/» glyphs with aria-labels.
- connecting, renameOk, renameCancel, home: no legacy counterpart.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import i18n_resources

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "seatunnel" / "src"
I18N_TS = SRC / "i18n.ts"

# React key -> {en, zh} legacy wording, verbatim from 5b42cf0 ui.py.
LEGACY_EXPECTED: dict[str, dict[str, str]] = {
    "title": {"en": "SeaTunnel Pipeline Builder", "zh": "SeaTunnel 数据管道构建器"},
    "subtitle": {"en": "AI Agent · ReAct Pattern · Auto-diagnose & Fix",
                 "zh": "AI 智能代理 · ReAct 推理模式 · 自动诊断修复"},
    "mode": {"en": "MODE", "zh": "运行模式"},
    "templates": {"en": "TEMPLATES", "zh": "配置模板"},
    "configPath": {"en": "CONFIG / LOG PATH", "zh": "配置 / 日志路径"},
    "connect": {"en": "Connect", "zh": "连接"},
    "status": {"en": "STATUS", "zh": "状态"},
    "statusDefault": {"en": "Not connected", "zh": "未连接"},
    "tplNone": {"en": "-- Select a template --", "zh": "-- 选择模板 --"},
    "inputPlaceholder": {"en": "Message SeaTunnel Agent...",
                         "zh": "输入你的数据管道任务..."},
    "send": {"en": "Send", "zh": "发送"},  # legacy key: submit
    "demo": {"en": "Demo", "zh": "演示"},
    "stop": {"en": "Stop", "zh": "停止"},
    "rename": {"en": "Rename", "zh": "重命名"},
    "delete": {"en": "Delete", "zh": "删除"},
    "export": {"en": "Export", "zh": "导出"},
    # legacy new_chat was "+ New Chat"/"+ 新建对话"; the "+" lives on the
    # button glyph in React (Sessions.tsx renders "+" with this aria-label)
    "newChat": {"en": "New Chat", "zh": "新建对话"},
    "sessions": {"en": "History", "zh": "历史记录"},  # legacy key: history
    "noSessions": {"en": "No conversations yet", "zh": "暂无历史记录"},
    "chatEmpty": {"en": "How can I help you build a pipeline?",
                  "zh": "我能帮你构建什么管道？"},  # legacy: placeholder_title
    "demoDefaultMsg": {"en": "Generate a FakeSource to Console config",
                       "zh": "帮我生成一个 FakeSource 到 Console 的配置"},
    "renamePlaceholder": {"en": "New name...", "zh": "新名称..."},
    "placeholderHint1": {"en": "Generate 10 fake rows to console",
                         "zh": "生成 10 条假数据到控制台"},
    "placeholderHint2": {"en": "Sync MySQL users table to Console",
                         "zh": "同步 MySQL 用户表到 Console"},
    "placeholderHint3": {"en": "Validate examples/fake_to_console.conf",
                         "zh": "验证 examples/fake_to_console.conf"},
    # ui.py:803-804 _handle_connect success f-strings
    "connected": {"en": "✅ Connected, Model: {{model}}",
                  "zh": "✅ 连接成功，模型: {{model}}"},
    # ui.py:807-809 _handle_connect failure f-strings
    # Glyph moved out of the string: ❌ is prepended at render time (uitest/sql_review convention).
    "connectFailed": {"en": "Failed: {{error}}", "zh": "连接失败: {{error}}"},
    # ui.py:226-227 _template_to_prompt f-strings
    "templatePrompt": {
        "en": "Create a pipeline config using the {{name}} template ({{params}})",
        "zh": "使用 {{name}} 模板创建管道配置（{{params}}）",
    },
    # ui.py:632-633: these two were English in BOTH locales in the legacy
    # page (the f-strings had no lang branch) — kept identical on purpose
    "errorLabel": {"en": "⚠️ **Error**: {{msg}}", "zh": "⚠️ **Error**: {{msg}}"},
    "completedIn": {"en": "⏱️ Completed in {{s}}s", "zh": "⏱️ Completed in {{s}}s"},
    # ui.py:689 docs_text branches
    "docsLink": {"en": "📖 Docs — View documentation", "zh": "📖 Docs — 查看使用文档"},
}


def test_en_zh_key_sets_match() -> None:
    res = i18n_resources(I18N_TS)
    assert res["en"], "no keys parsed from i18n.ts"
    assert set(res["en"]) == set(res["zh"])


def test_every_t_usage_is_defined() -> None:
    keys = set(i18n_resources(I18N_TS)["en"])
    used: set[str] = set()
    for tsx in SRC.glob("*.tsx"):
        used |= set(re.findall(r"\bt\('(\w+)'", tsx.read_text(encoding="utf-8")))
    assert used, "no t() usages found — glob broken?"
    missing = used - keys
    assert not missing, f"t() keys missing from i18n.ts: {sorted(missing)}"


def test_ported_keys_match_legacy_verbatim() -> None:
    res = i18n_resources(I18N_TS)
    problems: list[str] = []
    for react_key, expected_by_lang in LEGACY_EXPECTED.items():
        for lang in ("en", "zh"):
            got = res[lang].get(react_key)
            if got != expected_by_lang[lang]:
                problems.append(
                    f"{lang}.{react_key}: {got!r} != legacy {expected_by_lang[lang]!r}")
    assert not problems, "\n".join(problems)


def test_new_chat_plus_glyph_lives_on_button() -> None:
    """Legacy new_chat carried a leading '+ '; in React the '+' is the
    button's visible glyph (aria-label = newChat wording without it)."""
    sessions = (SRC / "Sessions.tsx").read_text(encoding="utf-8")
    m = re.search(r"aria-label=\{t\('newChat'\)\}.*?>\s*\+\s*</button>",
                  sessions, re.S)
    assert m, "new-chat button must render the '+' glyph with newChat aria-label"


def test_backend_i18n_holds_only_backend_rendered_keys() -> None:
    """rendering.I18N keeps only what the API renders; chrome keys pruned."""
    from seatunnel_agent.agents.data.seatunnel.rendering import I18N

    expected = {"mode_nl", "mode_run", "mode_validate", "mode_diagnose",
                "no_settings", "stopped",
                "demo_validate_done", "demo_general_done", "demo_failed"}
    assert set(I18N["en"]) == expected
    assert set(I18N["zh"]) == expected
