"""i18n parity for the React /ciinspect workspace.

Checks frontend/ci_inspect/src/i18n.ts (modeled on
tests/test_secret_scan_i18n.py):

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the legacy Gradio page carry the _I18N wording
  verbatim (expected values live INLINE below, copied from
  agents/devops/ci_inspect/ui.py).

Deviations (documented in i18n.ts): the legacy `title` markdown is split
into title (heading, 🧭 glyph moves next to the h1) + subtitle;
home/running are new chrome.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "ci_inspect" / "src"
I18N_TS = SRC / "i18n.ts"

LEGACY_EXPECTED: dict[str, dict[str, str]] = {
    "log_label": {"en": "Failed job log", "zh": "失败作业日志"},
    "log_ph": {"en": "Paste one job's log (GitHub Actions timestamps are "
                     "fine)…",
               "zh": "粘贴一个作业的日志(带 GitHub Actions 时间戳也可以)…"},
    "name_label": {"en": "Job name", "zh": "作业名"},
    "runs_acc": {"en": "Runs metadata (flaky & duration)",
                 "zh": "运行元数据(flaky 与时长)"},
    "runs_label": {"en": "Runs JSON", "zh": "Runs JSON"},
    "runs_ph": {"en": '[{"workflow":"tests","conclusion":"failure",'
                      '"head_sha":"abc1234","duration_s":312}, …]',
                "zh": '[{"workflow":"tests","conclusion":"failure",'
                      '"head_sha":"abc1234","duration_s":312}, …]'},
    "analyze_btn": {"en": "Analyze", "zh": "分析"},
    "report_ph": {"en": "▶ Root-cause clusters, flaky jobs and duration "
                        "drift appear here.",
                  "zh": "▶ 分析后在此显示根因聚类、flaky 作业与时长漂移。"},
    "empty": {"en": "⚠️ Paste a log or runs JSON first.",
              "zh": "⚠️ 请先粘贴日志或 runs JSON。"},
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
    files = list(SRC.glob("*.tsx"))
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
    # cookie-driven lng lives behind the shared seam now; the leaf only
    # declares resources (shared/src/i18n.ts carries langFromCookie)
    text = I18N_TS.read_text(encoding="utf-8")
    assert "initI18n(resources)" in text or "initI18n(" in text
    shared = (ROOT / "frontend" / "shared" / "src" / "i18n.ts").read_text(
        encoding="utf-8")
    assert re.search(r"lng:\s*langFromCookie\(\)", shared)
