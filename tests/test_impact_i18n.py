"""i18n parity for the React /impact workspace (ticket 02).

Checks frontend/change_impact/src/i18n.ts (modeled on
tests/test_lineage_i18n.py):

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the legacy Gradio page carry the _I18N wording
  verbatim (expected values live INLINE below, copied from the retired
  agents/data/data_lineage/ui_impact.py at 8ea9626^; {var} placeholders
  become i18next {{var}}).

Keys with documented deviations (noted in i18n.ts):
- title/subtitle: the legacy markdown blob is split, "## " and the 💥
  glyph move to the h1.
- result_ph: markdown *italics* wrappers dropped.
- running/home: busy state + hub nav (new chrome, precedent-consistent).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "change_impact" / "src"
I18N_TS = SRC / "i18n.ts"

LEGACY_EXPECTED: dict[str, dict[str, str]] = {
    "tab_dirs": {"en": "Directories", "zh": "目录模式"},
    "tab_paste": {"en": "Paste SQL", "zh": "粘贴 SQL"},
    "old_label": {"en": "Old SQL directory", "zh": "旧 SQL 目录"},
    "old_ph": {"en": "SQL tree before the change, e.g. examples/impact_demo/old",
               "zh": "变更前的 SQL 目录，如 examples/impact_demo/old"},
    "new_label": {"en": "New SQL directory", "zh": "新 SQL 目录"},
    "new_ph": {"en": "SQL tree after the change, e.g. examples/impact_demo/new",
               "zh": "变更后的 SQL 目录，如 examples/impact_demo/new"},
    "old_sql_label": {"en": "Old SQL", "zh": "旧 SQL"},
    "old_sql_ph": {"en": "Paste the SQL before the change…", "zh": "粘贴变更前的 SQL…"},
    "new_sql_label": {"en": "New SQL", "zh": "新 SQL"},
    "new_sql_ph": {"en": "Paste the SQL after the change…", "zh": "粘贴变更后的 SQL…"},
    "ctx_label": {"en": "Context SQL directory (optional)", "zh": "上下文 SQL 目录（可选）"},
    "ctx_ph": {"en": "Repo SQL tree; widens the blast radius to real consumers",
               "zh": "仓库 SQL 目录；填写后下游波及按全仓血缘计算"},
    "dialect_label": {"en": "SQL dialect", "zh": "SQL 方言"},
    "depth_label": {"en": "Downstream depth", "zh": "下游深度"},
    "analyze_btn": {"en": "Analyze change impact", "zh": "变更影响分析"},
    "analyze_sql_btn": {"en": "Analyze pasted SQL", "zh": "分析粘贴的 SQL"},
    "need_dirs": {"en": "⚠️ Provide both the old and the new SQL directory.",
                  "zh": "⚠️ 请同时填写旧、新两个 SQL 目录。"},
    "need_sql": {"en": "⚠️ Paste both the old and the new SQL.",
                 "zh": "⚠️ 请同时粘贴旧、新两段 SQL。"},
    "bad_dir": {"en": "❌ Not a directory: `{{d}}`", "zh": "❌ 不是有效目录: `{{d}}`"},
    "fail": {"en": "❌ **Analysis failed**: {{exc}}", "zh": "❌ **分析失败**: {{exc}}"},
}


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


def test_i18n_initialized_from_lang_cookie() -> None:
    text = I18N_TS.read_text(encoding="utf-8")
    assert "langFromCookie" in text
    assert re.search(r"lng:\s*langFromCookie\(\)", text)


def test_dialect_list_pinned_to_backend() -> None:
    # App.tsx hardcodes the dialect list — pin it to sqlglot_lineage's
    # SQL_DIALECTS so a backend change fails here instead of drifting
    from seatunnel_agent.agents.data.data_lineage.sqlglot_lineage import (
        SQL_DIALECTS,
    )

    app = (SRC / "App.tsx").read_text(encoding="utf-8")
    m = re.search(r"const SQL_DIALECTS = \[(.*?)\]", app, re.S)
    assert m, "SQL_DIALECTS literal not found in App.tsx"
    ts_list = re.findall(r"'([a-z]+)'", m.group(1))
    assert ts_list == list(SQL_DIALECTS)
