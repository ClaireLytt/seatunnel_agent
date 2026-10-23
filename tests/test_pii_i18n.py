"""i18n parity for the React /pii workspace (ticket 02).

Checks frontend/pii_scan/src/i18n.ts (modeled on
tests/test_metricdiff_i18n.py):

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the legacy Gradio page carry the _I18N wording
  verbatim (expected values live INLINE below, copied from the retired
  agents/data/pii_scan/ui.py);
- the hardcoded dialect list and demo prefill are pinned.

Deviations (documented in i18n.ts): title/subtitle split (🔒 glyph moves
next to the h1); the legacy `result_label` key was defined but unused in
the layout — dropped; home/running are new chrome.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import i18n_resources, workspace_sources

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "pii_scan" / "src"
I18N_TS = SRC / "i18n.ts"

LEGACY_EXPECTED: dict[str, dict[str, str]] = {
    "dir_label": {"en": "SQL directory", "zh": "SQL 目录"},
    "dir_ph": {"en": "Directory containing *.sql files (scanned recursively), "
                     "e.g. examples/pii_demo",
               "zh": "包含 *.sql 的目录（递归扫描），如 examples/pii_demo"},
    "dialect_label": {"en": "SQL dialect", "zh": "SQL 方言"},
    "scan_btn": {"en": "Scan directory", "zh": "扫描目录"},
    "inline_acc": {"en": "Scan pasted SQL", "zh": "扫描粘贴的 SQL"},
    "sql_label": {"en": "SQL input", "zh": "SQL 输入"},
    "sql_ph": {"en": "Paste CREATE TABLE / INSERT ... SELECT statements…",
               "zh": "粘贴 CREATE TABLE / INSERT ... SELECT 语句…"},
    "scan_sql_btn": {"en": "Scan SQL", "zh": "扫描 SQL"},
    "empty_dir": {"en": "⚠️ Provide a SQL directory first.",
                  "zh": "⚠️ 请先填写 SQL 目录。"},
    "bad_dir": {"en": "⚠️ Not a directory: ", "zh": "⚠️ 不是有效目录: "},
    "empty_sql": {"en": "⚠️ Paste some SQL first.", "zh": "⚠️ 请先粘贴 SQL。"},
}

LEGACY_DIALECTS = ["hive", "spark", "mysql", "postgresql", "clickhouse",
                   "doris", "starrocks"]


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


def test_dialect_list_pinned_to_legacy() -> None:
    constants = (ROOT / "frontend" / "shared" / "src" / "constants.ts").read_text(encoding="utf-8")
    m = re.search(r"const DIALECTS = \[(.*?)\]", constants, re.S)
    assert m, "DIALECTS literal not found in shared/constants.ts"
    assert re.findall(r"'([a-z]+)'", m.group(1)) == LEGACY_DIALECTS


def test_demo_dir_prefill_matches_legacy() -> None:
    app = (SRC / "App.tsx").read_text(encoding="utf-8")
    assert "examples/pii_demo" in app


def test_i18n_initialized_via_shared_initI18n() -> None:
    # cookie-driven lng lives behind the shared seam now; the leaf only
    # declares resources (shared/src/i18n.ts carries langFromCookie)
    text = I18N_TS.read_text(encoding="utf-8")
    assert "initI18n(resources)" in text or "initI18n(" in text
    shared = (ROOT / "frontend" / "shared" / "src" / "i18n.ts").read_text(
        encoding="utf-8")
    assert re.search(r"lng:\s*langFromCookie\(\)", shared)
