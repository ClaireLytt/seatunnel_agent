"""i18n parity for the React /testgen workspace (ticket 02).

Checks frontend/sql_testgen/src/i18n.ts (modeled on
tests/test_sqlfmt_i18n.py):

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the legacy Gradio page carry the _I18N wording
  verbatim (expected values live INLINE below, copied from the retired
  agents/data/sql_testgen/ui.py at 7bb5f5f^, so the React side stays
  pinned after the retirement).

Keys with no legacy wording to check (new UI text on the React page):
- title/subtitle: the legacy `title` was one markdown blob
  "## 🧪 SQL Test Data Generator\\n<body>"; React splits it into an h1
  (drops the markdown "## " — the 🧪 glyph moves next to the h1) +
  subtitle paragraph.
- home: hub navigation link (the Gradio shell provided its own nav).
- running: busy state of the generate button (legacy had none).

Backend-rendered keys (report wording) stay in Python report.py and reach
the page already localized inside the report markdown — they are
deliberately NOT in i18n.ts.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import i18n_resources, workspace_sources

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "sql_testgen" / "src"
I18N_TS = SRC / "i18n.ts"

# React key -> {en, zh} legacy wording, verbatim from _I18N
# (retired src/.../sql_testgen/ui.py, git 7bb5f5f^).
LEGACY_EXPECTED: dict[str, dict[str, str]] = {
    "sql_label": {"en": "Query SQL", "zh": "查询 SQL"},
    "sql_ph": {"en": "Paste the SELECT / INSERT...SELECT to generate data for…",
               "zh": "粘贴需要造数的 SELECT / INSERT...SELECT…"},
    "ddl_label": {"en": "DDL (optional)", "zh": "DDL（可选）"},
    "ddl_ph": {"en": "CREATE TABLE statements for exact column types…",
               "zh": "粘贴 CREATE TABLE 以获得精确的列类型…"},
    "dialect_label": {"en": "SQL dialect", "zh": "SQL 方言"},
    "rows_label": {"en": "Rows per table", "zh": "每表行数"},
    "validate_label": {"en": "Validate on SQLite", "zh": "SQLite 验证"},
    "gen_btn": {"en": "Generate", "zh": "生成测试数据"},
    "empty_sql": {"en": "⚠️ Paste a query first.", "zh": "⚠️ 请先粘贴查询 SQL。"},
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


def test_demo_sql_prefill_matches_legacy() -> None:
    # TGN1/TGN2 depend on the demo prefill — pin it to the legacy _DEMO_SQL
    app = (SRC / "App.tsx").read_text(encoding="utf-8")
    for fragment in ("dwd.user_info", "dwd.order_pay",
                     "o.dt = '2024-01-01'", "('PAID', 'DONE')"):
        assert fragment in app, f"demo SQL fragment missing: {fragment}"


def test_i18n_initialized_via_shared_initI18n() -> None:
    # cookie-driven lng lives behind the shared seam now; the leaf only
    # declares resources (shared/src/i18n.ts carries langFromCookie)
    text = I18N_TS.read_text(encoding="utf-8")
    assert "initI18n(resources)" in text or "initI18n(" in text
    shared = (ROOT / "frontend" / "shared" / "src" / "i18n.ts").read_text(
        encoding="utf-8")
    assert re.search(r"lng:\s*langFromCookie\(\)", shared)
