"""i18n parity for the React /dagcheck workspace (ticket 02).

Checks frontend/dag_check/src/i18n.ts (modeled on
tests/test_metricdiff_i18n.py):

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the legacy Gradio page carry the _I18N wording
  verbatim (expected values live INLINE below, copied from the retired
  agents/data/dag_check/ui.py);
- the hardcoded dialect list and demo prefill are pinned;
- Python report i18n (i18n.py DAG_I18N) en/zh key sets also match —
  the report arrives pre-localized from the server, so its keys live
  there, not in i18n.ts.

Keys with no legacy wording (new chrome, precedent-consistent):
title/subtitle split (the 🗓️ glyph moves next to the h1), home, running.
"""

from __future__ import annotations

import re
from pathlib import Path

from seatunnel_agent.agents.data.dag_check.i18n import DAG_I18N

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "dag_check" / "src"
I18N_TS = SRC / "i18n.ts"

LEGACY_EXPECTED: dict[str, dict[str, str]] = {
    "dir_label": {"en": "SQL directory", "zh": "SQL 目录"},
    "dir_ph": {"en": "Directory containing *.sql (scanned recursively), "
                     "e.g. examples/dagcheck_demo",
               "zh": "包含 *.sql 的目录（递归扫描），如 examples/dagcheck_demo"},
    "st_label": {"en": "SeaTunnel config directory (optional)",
                 "zh": "SeaTunnel 配置目录（可选）"},
    "st_ph": {"en": "Merge source→sink lineage from *.conf files",
              "zh": "合并 *.conf 的 source→sink 血缘"},
    "dialect_label": {"en": "SQL dialect", "zh": "SQL 方言"},
    "check_btn": {"en": "Check DAG", "zh": "体检 DAG"},
    "empty_dir": {"en": "⚠️ Provide a SQL directory first.",
                  "zh": "⚠️ 请先填写 SQL 目录。"},
    "bad_dir": {"en": "⚠️ Not a directory: ", "zh": "⚠️ 不是有效目录: "},
}

LEGACY_DIALECTS = ["hive", "spark", "mysql", "postgresql", "clickhouse",
                   "doris", "starrocks"]


def _parse_locale(block: str) -> dict[str, str]:
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


def test_dialect_list_pinned_to_legacy() -> None:
    app = (SRC / "App.tsx").read_text(encoding="utf-8")
    m = re.search(r"const DIALECTS = \[(.*?)\]", app, re.S)
    assert m, "DIALECTS literal not found in App.tsx"
    assert re.findall(r"'([a-z]+)'", m.group(1)) == LEGACY_DIALECTS


def test_demo_dir_prefill_matches_legacy() -> None:
    app = (SRC / "App.tsx").read_text(encoding="utf-8")
    assert "examples/dagcheck_demo" in app


def test_i18n_initialized_via_shared_initI18n() -> None:
    # cookie-driven lng lives behind the shared seam now; the leaf only
    # declares resources (shared/src/i18n.ts carries langFromCookie)
    text = I18N_TS.read_text(encoding="utf-8")
    assert "initI18n(resources)" in text or "initI18n(" in text
    shared = (ROOT / "frontend" / "shared" / "src" / "i18n.ts").read_text(
        encoding="utf-8")
    assert re.search(r"lng:\s*langFromCookie\(\)", shared)


def test_python_report_i18n_key_sets_match() -> None:
    assert set(DAG_I18N["en"]) == set(DAG_I18N["zh"])
    assert DAG_I18N["en"], "DAG_I18N en block empty"
    # report keys stay server-side: none of them leak into i18n.ts
    assert not set(DAG_I18N["en"]) & set(_resources()["en"])
