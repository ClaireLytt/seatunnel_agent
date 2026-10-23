"""i18n parity for the React /metricdiff workspace (ticket 02).

Checks frontend/metric_diff/src/i18n.ts (modeled on
tests/test_schemadrift_i18n.py):

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the legacy Gradio page carry the _I18N wording
  verbatim (expected values live INLINE below, copied from the retired
  agents/data/metric_diff/ui.py);
- the hardcoded dialect list and demo prefill are pinned.

Keys with no legacy wording (new chrome, precedent-consistent):
title/subtitle split (the 📏 glyph moves next to the h1), home, running.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import i18n_resources, workspace_sources

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "metric_diff" / "src"
I18N_TS = SRC / "i18n.ts"

LEGACY_EXPECTED: dict[str, dict[str, str]] = {
    "dir_label": {"en": "SQL directory", "zh": "SQL 目录"},
    "dir_ph": {"en": "Directory containing *.sql (scanned recursively), "
                     "e.g. examples/metricdiff_demo",
               "zh": "包含 *.sql 的目录（递归扫描），如 examples/metricdiff_demo"},
    "dialect_label": {"en": "SQL dialect", "zh": "SQL 方言"},
    "check_btn": {"en": "Check metrics", "zh": "检查口径"},
    "empty_dir": {"en": "⚠️ Provide a SQL directory first.",
                  "zh": "⚠️ 请先填写 SQL 目录。"},
    "bad_dir": {"en": "⚠️ Not a directory: ", "zh": "⚠️ 不是有效目录: "},
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
    assert "examples/metricdiff_demo" in app


def test_i18n_initialized_via_shared_initI18n() -> None:
    # cookie-driven lng lives behind the shared seam now; the leaf only
    # declares resources (shared/src/i18n.ts carries langFromCookie)
    text = I18N_TS.read_text(encoding="utf-8")
    assert "initI18n(resources)" in text or "initI18n(" in text
    shared = (ROOT / "frontend" / "shared" / "src" / "i18n.ts").read_text(
        encoding="utf-8")
    assert re.search(r"lng:\s*langFromCookie\(\)", shared)
