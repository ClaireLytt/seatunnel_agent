"""i18n parity for the React /migrate workspace (ticket 04).

Checks frontend/config_migrate/src/i18n.ts (modeled on
tests/test_datacompare_i18n.py):

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the legacy Gradio page carry the _I18N wording
  verbatim (expected values live INLINE below, copied from the retired
  agents/data/config_migrate/ui.py at cb35e09, so the React side stays
  pinned after the ticket 03 retirement).

Keys with no legacy wording to check (new UI text on the React page):
- title/subtitle: the legacy `title` was one markdown blob
  "## 🚚 DataX/Sqoop → SeaTunnel\\n<body>"; React splits it into an h1
  (drops the markdown "## " and the 🚚 glyph) + subtitle paragraph.
- home: hub navigation link (the Gradio shell provided its own nav).
- copy/copied: the ConfView copy button (gr.Code had a built-in one).
- running: busy state of the migrate/batch buttons (legacy had none).

Backend-rendered keys (report wording like unknown_format / stats) stay
in Python report.py _MSG and reach the page already localized inside
the report markdown — they are deliberately NOT in i18n.ts.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "config_migrate" / "src"
I18N_TS = SRC / "i18n.ts"

# React key -> {en, zh} legacy wording, verbatim from _I18N
# (retired src/.../config_migrate/ui.py, git cb35e09).
LEGACY_EXPECTED: dict[str, dict[str, str]] = {
    "job_label": {"en": "DataX job JSON / sqoop command",
                  "zh": "DataX job JSON / sqoop 命令"},
    "job_ph": {"en": "Paste the DataX job json, or e.g. sqoop import --connect …",
               "zh": "粘贴 DataX job json，或如 sqoop import --connect …"},
    "migrate_btn": {"en": "Migrate", "zh": "迁移"},
    "batch_acc": {"en": "Batch migrate a directory", "zh": "批量迁移目录"},
    "dir_label": {"en": "Job directory", "zh": "任务目录"},
    "dir_ph": {"en": "Directory with *.json / sqoop scripts (recursive)",
               "zh": "包含 *.json / sqoop 脚本的目录（递归）"},
    "out_label": {"en": "Output directory (optional)", "zh": "输出目录（可选）"},
    "out_ph": {"en": "Writes mirrored *.conf files when set",
               "zh": "填写后按原结构写出 *.conf"},
    "batch_btn": {"en": "Batch migrate", "zh": "批量迁移"},
    "conf_label": {"en": "SeaTunnel config", "zh": "SeaTunnel 配置"},
    "empty": {"en": "⚠️ Paste a DataX job or sqoop command first.",
              "zh": "⚠️ 请先粘贴 DataX job 或 sqoop 命令。"},
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


def test_i18n_initialized_via_shared_initI18n() -> None:
    # cookie-driven lng lives behind the shared seam now; the leaf only
    # declares resources (shared/src/i18n.ts carries langFromCookie)
    text = I18N_TS.read_text(encoding="utf-8")
    assert "initI18n(resources)" in text or "initI18n(" in text
    shared = (ROOT / "frontend" / "shared" / "src" / "i18n.ts").read_text(
        encoding="utf-8")
    assert re.search(r"lng:\s*langFromCookie\(\)", shared)
