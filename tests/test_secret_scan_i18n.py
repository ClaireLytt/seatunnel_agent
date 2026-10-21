"""i18n parity for the React /secretscan workspace.

Checks frontend/secret_scan/src/i18n.ts (modeled on tests/test_pii_i18n.py):

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the legacy Gradio page carry the _I18N wording
  verbatim (expected values live INLINE below, copied from the retired
  agents/devops/secret_scan/ui.py).

Deviations (documented in i18n.ts): title/subtitle split (🔑 glyph moves
next to the h1; the legacy CI-gate sentence moves to the dir_hint card);
directory scanning stays a CLI affair (the REST API refuses to walk
directories), so dir_acc/dir_label/dir_ph/dir_btn/empty_dir/bad_dir are
replaced by one dir_hint key; home/running are new chrome.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "secret_scan" / "src"
I18N_TS = SRC / "i18n.ts"

LEGACY_EXPECTED: dict[str, dict[str, str]] = {
    "text_label": {"en": "Text to scan", "zh": "待扫描文本"},
    "text_ph": {"en": "Paste a config / env file / code snippet…",
                "zh": "粘贴配置 / env 文件 / 代码片段…"},
    "scan_btn": {"en": "Scan", "zh": "扫描"},
    "report_ph": {"en": "▶ Findings appear here — severity, rule, file:line "
                        "and a masked preview.",
                  "zh": "▶ 扫描后在此显示结果 — 严重度、规则、文件:行号与"
                        "脱敏预览。"},
    "empty_text": {"en": "⚠️ Paste some text first.", "zh": "⚠️ 请先粘贴文本。"},
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


def test_cli_gate_command_pinned() -> None:
    app = (SRC / "App.tsx").read_text(encoding="utf-8")
    assert "seatunnel-agent secretscan --fail-on high" in app


def test_i18n_initialized_from_lang_cookie() -> None:
    text = I18N_TS.read_text(encoding="utf-8")
    assert "langFromCookie" in text
    assert re.search(r"lng:\s*langFromCookie\(\)", text)
