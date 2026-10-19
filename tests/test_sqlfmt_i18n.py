"""i18n parity for the React /sqlfmt workspace (ticket 02).

Checks frontend/sql_fmt/src/i18n.ts (modeled on tests/test_conflint_i18n.py):

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the legacy Gradio page carry the _I18N wording
  verbatim (expected values live INLINE below, copied from the retired
  agents/data/sql_fmt/ui.py at dfd14b2^, so the React side stays pinned
  after the retirement).

Keys with no legacy wording to check (new UI text on the React page):
- title/subtitle: the legacy `title` was one markdown blob
  "## 🪄 SQL Formatter\\n<body>"; React splits it into an h1 (drops the
  markdown "## " — the 🪄 glyph moves next to the h1) + subtitle paragraph.
- home: hub navigation link (the Gradio shell provided its own nav).
- running: busy state of the format buttons (legacy had none).

Backend-rendered keys (report wording like rpt_unchanged / rpt_select_star)
stay in Python i18n.py and reach the page already localized inside the
report markdown — they are deliberately NOT in i18n.ts.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "sql_fmt" / "src"
I18N_TS = SRC / "i18n.ts"

# React key -> {en, zh} legacy wording, verbatim from _I18N
# (retired src/.../sql_fmt/ui.py, git dfd14b2^).
LEGACY_EXPECTED: dict[str, dict[str, str]] = {
    "sql_label": {"en": "SQL input", "zh": "SQL 输入"},
    "sql_ph": {"en": "Paste one or more ;-separated statements…",
               "zh": "粘贴一条或多条以 ; 分隔的 SQL…"},
    "dialect_label": {"en": "SQL dialect", "zh": "SQL 方言"},
    "fmt_btn": {"en": "Format", "zh": "格式化"},
    "dir_acc": {"en": "Check a directory", "zh": "检查目录"},
    "dir_label": {"en": "SQL directory", "zh": "SQL 目录"},
    "dir_ph": {"en": "Directory containing *.sql (scanned recursively), "
                     "e.g. examples/sqlfmt_demo",
               "zh": "包含 *.sql 的目录（递归扫描），如 examples/sqlfmt_demo"},
    "dir_btn": {"en": "Check directory", "zh": "检查目录"},
    "empty_sql": {"en": "⚠️ Paste some SQL first.", "zh": "⚠️ 请先粘贴 SQL。"},
    "empty_dir": {"en": "⚠️ Provide a SQL directory first.",
                  "zh": "⚠️ 请先填写 SQL 目录。"},
    "bad_dir": {"en": "⚠️ Not a directory: ", "zh": "⚠️ 不是有效目录: "},
}


def _parse_locale(block: str) -> dict[str, str]:
    # keys may be multi-part string concatenations ('a ' + 'b'); join them
    pairs = re.findall(
        r"(\w+):\s*((?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|\s|\+)+)",
        block,
    )
    out: dict[str, str] = {}
    for key, raw in pairs:
        chunks = re.findall(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"", raw)
        val = "".join(a if a else b for a, b in chunks)
        out[key] = (val.replace("\\'", "'").replace('\\"', '"')
                    .replace("\\n", "\n"))
    return out


def _resources() -> dict[str, dict[str, str]]:
    text = I18N_TS.read_text(encoding="utf-8")
    locales = re.findall(
        r"^  (en|zh): \{\s*translation: \{(.*?)^    \},\s*^  \},",
        text,
        re.S | re.M,
    )
    assert {name for name, _ in locales} == {"en", "zh"}, "en/zh blocks not found"
    return {name: _parse_locale(body) for name, body in locales}


def _workspace_sources() -> list[str]:
    files = list(SRC.glob("*.tsx")) + list((SRC / "components").glob("*.tsx"))
    assert files, "no .tsx files found — glob broken?"
    return [f.read_text(encoding="utf-8") for f in files]


def test_en_zh_key_sets_match() -> None:
    res = _resources()
    assert res["en"], "no keys parsed from i18n.ts"
    assert set(res["en"]) == set(res["zh"])


def test_every_t_usage_is_defined() -> None:
    keys = set(_resources()["en"])
    used: set[str] = set()
    for text in _workspace_sources():
        used |= set(re.findall(r"\bt\('(\w+)'", text))
    assert used, "no t() usages found — glob broken?"
    missing = used - keys
    assert not missing, f"t() keys missing from i18n.ts: {sorted(missing)}"


def test_ported_keys_match_legacy_verbatim() -> None:
    res = _resources()
    problems: list[str] = []
    for react_key, expected_by_lang in LEGACY_EXPECTED.items():
        for lang in ("en", "zh"):
            got = res[lang].get(react_key)
            if got != expected_by_lang[lang]:
                problems.append(
                    f"{lang}.{react_key}: {got!r} != legacy {expected_by_lang[lang]!r}")
    assert not problems, "\n".join(problems)


def test_i18n_initialized_from_lang_cookie() -> None:
    text = I18N_TS.read_text(encoding="utf-8")
    assert "langFromCookie" in text
    assert re.search(r"lng:\s*langFromCookie\(\)", text)
