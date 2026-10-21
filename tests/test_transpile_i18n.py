"""i18n parity for the React /transpile workspace (ticket 02).

Checks frontend/sql_transpile/src/i18n.ts (modeled on
tests/test_sqlfmt_i18n.py):

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the legacy Gradio page carry the _I18N wording
  verbatim (expected values live INLINE below, copied from the retired
  agents/data/sql_transpile/ui.py at 7ed9410^, so the React side stays
  pinned after the retirement).

Keys with no legacy wording to check (new UI text on the React page):
- title/subtitle: the legacy `title` was one markdown blob
  "## 🔁 SQL Dialect Translation\\n<body>"; React splits it into an h1
  (drops the markdown "## " — the 🔁 glyph moves next to the h1) +
  subtitle paragraph.
- advice_none/advice_no_key: legacy wrapped them in markdown *italics*;
  React renders them as plain i18n text, wording otherwise verbatim.
- home: hub navigation link (the Gradio shell provided its own nav).
- copy/copied: the SqlView copy button (gr.Code had a built-in one).
- running/advising: busy states of the buttons (legacy had none).

Backend-rendered keys (issue/report wording) stay in Python i18n.py and
reach the page already localized inside the report markdown — they are
deliberately NOT in i18n.ts.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "sql_transpile" / "src"
I18N_TS = SRC / "i18n.ts"

# React key -> {en, zh} legacy wording, verbatim from _I18N
# (retired src/.../sql_transpile/ui.py, git 7ed9410^).
LEGACY_EXPECTED: dict[str, dict[str, str]] = {
    "src_label": {"en": "Source dialect", "zh": "源方言"},
    "src_auto": {"en": "Auto detect", "zh": "自动推断"},
    "dst_label": {"en": "Target dialect", "zh": "目标方言"},
    "sql_label": {"en": "SQL input", "zh": "SQL 输入"},
    "sql_ph": {"en": "Paste one or more ;-separated statements…",
               "zh": "粘贴一条或多条以 ; 分隔的 SQL…"},
    "translate_btn": {"en": "Translate", "zh": "翻译"},
    "batch_acc": {"en": "Batch translate a directory", "zh": "批量翻译目录"},
    "dir_label": {"en": "SQL directory", "zh": "SQL 目录"},
    "dir_ph": {"en": "Directory containing *.sql files (scanned recursively)",
               "zh": "包含 *.sql 的目录（递归扫描）"},
    "out_label": {"en": "Output directory (optional)", "zh": "输出目录（可选）"},
    "out_ph": {"en": "Translated files mirror the input tree when set",
               "zh": "填写后按原目录结构写出翻译文件"},
    "batch_btn": {"en": "Batch translate", "zh": "批量翻译"},
    "result_label": {"en": "Translated SQL", "zh": "翻译后 SQL"},
    "empty_sql": {"en": "⚠️ Paste some SQL first.", "zh": "⚠️ 请先粘贴 SQL。"},
    "empty_dir": {"en": "⚠️ Provide a SQL directory first.",
                  "zh": "⚠️ 请先填写 SQL 目录。"},
    "bad_dir": {"en": "⚠️ Not a directory: ", "zh": "⚠️ 不是有效目录: "},
    "advice_acc": {"en": "LLM advice (optional, llm-generated)",
                   "zh": "LLM 建议（可选，llm-generated）"},
    "advice_btn": {"en": "Generate LLM advice", "zh": "生成 LLM 建议"},
    # legacy wrapped these two in markdown *italics* — wording pinned
    # without the asterisks (React renders them as plain text)
    "advice_none": {"en": "No findings that need LLM advice.",
                    "zh": "没有需要 LLM 建议的不兼容点。"},
    "advice_no_key": {
        "en": "No API key configured — deterministic results above are unaffected.",
        "zh": "未配置 API key — 上方确定性结果不受影响。"},
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


def test_i18n_initialized_via_shared_initI18n() -> None:
    # cookie-driven lng lives behind the shared seam now; the leaf only
    # declares resources (shared/src/i18n.ts carries langFromCookie)
    text = I18N_TS.read_text(encoding="utf-8")
    assert "initI18n(resources)" in text or "initI18n(" in text
    shared = (ROOT / "frontend" / "shared" / "src" / "i18n.ts").read_text(
        encoding="utf-8")
    assert re.search(r"lng:\s*langFromCookie\(\)", shared)
