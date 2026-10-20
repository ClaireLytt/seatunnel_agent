"""i18n parity for the React /schemadrift workspace (ticket 02).

Checks frontend/schema_drift/src/i18n.ts (modeled on
tests/test_sqlfmt_i18n.py):

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the legacy Gradio page carry the _I18N wording
  verbatim (expected values live INLINE below, copied from the retired
  agents/data/schema_drift/ui.py at da904f0^);
- the hardcoded dialect list is pinned to the legacy tuple.

Keys with no legacy wording (new chrome, precedent-consistent):
title/subtitle split (the 🧬 glyph moves next to the h1), home, running.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "schema_drift" / "src"
I18N_TS = SRC / "i18n.ts"

LEGACY_EXPECTED: dict[str, dict[str, str]] = {
    "dialect_label": {"en": "SQL dialect", "zh": "SQL 方言"},
    "old_label": {"en": "Old DDL", "zh": "旧版 DDL"},
    "old_ph": {"en": "Paste the old CREATE TABLE script…",
               "zh": "粘贴旧版 CREATE TABLE 脚本…"},
    "new_label": {"en": "New DDL", "zh": "新版 DDL"},
    "new_ph": {"en": "Paste the new CREATE TABLE script…",
               "zh": "粘贴新版 CREATE TABLE 脚本…"},
    "diff_btn": {"en": "Compare", "zh": "对比"},
    "dirs_acc": {"en": "Compare two directories", "zh": "对比两个目录"},
    "old_dir_label": {"en": "Old directory / file", "zh": "旧目录 / 文件"},
    "new_dir_label": {"en": "New directory / file", "zh": "新目录 / 文件"},
    "dirs_btn": {"en": "Compare directories", "zh": "对比目录"},
    "empty_sql": {"en": "⚠️ Paste both DDL scripts first.",
                  "zh": "⚠️ 请先粘贴两份 DDL。"},
    "empty_dirs": {"en": "⚠️ Provide both paths first.",
                   "zh": "⚠️ 请先填写两个路径。"},
    "bad_path": {"en": "⚠️ Path does not exist: ", "zh": "⚠️ 路径不存在: "},
}

# Legacy _DIALECTS tuple (retired ui.py) — the React copy must match it
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
    constants = (ROOT / "frontend" / "shared" / "src" / "constants.ts").read_text(encoding="utf-8")
    m = re.search(r"const DIALECTS = \[(.*?)\]", constants, re.S)
    assert m, "DIALECTS literal not found in shared/constants.ts"
    ts_list = re.findall(r"'([a-z]+)'", m.group(1))
    assert ts_list == LEGACY_DIALECTS


def test_demo_dir_prefill_matches_legacy() -> None:
    # SDF1 depends on the prefilled demo paths
    app = (SRC / "App.tsx").read_text(encoding="utf-8")
    assert "examples/schema_drift_demo/old" in app
    assert "examples/schema_drift_demo/new" in app


def test_i18n_initialized_from_lang_cookie() -> None:
    text = I18N_TS.read_text(encoding="utf-8")
    assert "langFromCookie" in text
    assert re.search(r"lng:\s*langFromCookie\(\)", text)
