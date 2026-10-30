"""i18n parity for the React /conflint workspace (ticket 02).

Checks frontend/config_lint/src/i18n.ts (modeled on
tests/test_config_migrate_i18n.py):

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the legacy Gradio page carry the _I18N wording
  verbatim (expected values live INLINE below, copied from the retired
  agents/data/config_lint/ui.py at 1623dd9, so the React side stays
  pinned after the retirement).

Keys with no legacy wording to check (new UI text on the React page):
- title/subtitle: the legacy `title` was one markdown blob
  "## 🧰 SeaTunnel Config Lint\\n<body>"; React splits it into an h1
  (drops the markdown "## " — the 🧰 glyph moves next to the h1) +
  subtitle paragraph.
- home: hub navigation link (the Gradio shell provided its own nav).
- running: busy state of the lint buttons (legacy had none).

Backend-rendered keys (report wording like rpt_stats / msg_*) stay in
Python i18n.py CFL_I18N and reach the page already localized inside the
report markdown — they are deliberately NOT in i18n.ts.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import i18n_resources, workspace_sources

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "config_lint" / "src"
I18N_TS = SRC / "i18n.ts"

# React key -> {en, zh} legacy wording, verbatim from _I18N
# (retired src/.../config_lint/ui.py, git 1623dd9^).
LEGACY_EXPECTED: dict[str, dict[str, str]] = {
    "conf_label": {"en": "Config (HOCON)", "zh": "配置 (HOCON)"},
    "conf_ph": {"en": "Paste a SeaTunnel .conf…",
                "zh": "粘贴 SeaTunnel .conf 配置…"},
    "lint_btn": {"en": "Lint config", "zh": "检查配置"},
    "dir_acc": {"en": "Lint a directory", "zh": "检查整个目录"},
    "dir_label": {"en": "Config directory", "zh": "配置目录"},
    "dir_ph": {"en": "Directory containing *.conf (scanned recursively), "
                     "e.g. examples/conflint_demo",
               "zh": "包含 *.conf 的目录（递归扫描），如 examples/conflint_demo"},
    "dir_btn": {"en": "Lint directory", "zh": "检查目录"},
    "empty_conf": {"en": "Paste a config first.", "zh": "请先粘贴配置。"},
    "empty_dir": {"en": "Provide a config directory first.",
                  "zh": "请先填写配置目录。"},
    "bad_dir": {"en": "Not a directory: ", "zh": "不是有效目录: "},
}


def test_en_zh_key_sets_match() -> None:
    res = i18n_resources(I18N_TS)
    assert res["en"], "no keys parsed from i18n.ts"
    assert set(res["en"]) == set(res["zh"])


def test_every_t_usage_is_defined() -> None:
    keys = set(i18n_resources(I18N_TS)["en"])
    used: set[str] = set()
    for text in workspace_sources(SRC):
        used |= set(re.findall(r"\bt\('(\w+)'", text))
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


def test_i18n_initialized_via_shared_initI18n() -> None:
    # cookie-driven lng lives behind the shared seam now; the leaf only
    # declares resources (shared/src/i18n.ts carries langFromCookie)
    text = I18N_TS.read_text(encoding="utf-8")
    assert "initI18n(resources)" in text or "initI18n(" in text
    shared = (ROOT / "frontend" / "shared" / "src" / "i18n.ts").read_text(
        encoding="utf-8")
    assert re.search(r"lng:\s*langFromCookie\(\)", shared)
