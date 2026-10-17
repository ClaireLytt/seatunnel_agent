"""i18n parity for the React /seatunnel workspace (ticket 07).

Checks frontend/seatunnel/src/i18n.ts against the legacy Gradio page's
Python i18n dict (seatunnel.rendering._I18N) — the source of truth for wording:

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the legacy dict carry its values verbatim.
"""

from __future__ import annotations

import re
from pathlib import Path

from seatunnel_agent.agents.data.seatunnel.rendering import _I18N

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "seatunnel" / "src"
I18N_TS = SRC / "i18n.ts"

# React camelCase key -> legacy _I18N key (verbatim-ported wording)
LEGACY_MAP = {
    "title": "title",
    "subtitle": "subtitle",
    "mode": "mode",
    "templates": "templates",
    "configPath": "config_path",
    "connect": "connect",
    "status": "status",
    "statusDefault": "status_default",
    "tplNone": "tpl_none",
    "inputPlaceholder": "input_placeholder",
    "send": "submit",
    "demo": "demo",
    "stop": "stop",
    "rename": "rename",
    "delete": "delete",
    "export": "export",
    "newChat": "new_chat",  # legacy value carries a leading "+ " glyph
    "sessions": "history",
    "noSessions": "no_history",
    "chatEmpty": "placeholder_title",
    "demoDefaultMsg": "demo_default_msg",
    "renamePlaceholder": "rename_placeholder",
    "placeholderHint1": "placeholder_hint1",
    "placeholderHint2": "placeholder_hint2",
    "placeholderHint3": "placeholder_hint3",
}


def _parse_locale(block: str) -> dict[str, str]:
    pairs = re.findall(r"(\w+):\s*'((?:[^'\\]|\\.)*)'", block)
    return {k: v.replace("\\'", "'").replace("\\n", "\n") for k, v in pairs}


def _resources() -> dict[str, dict[str, str]]:
    text = I18N_TS.read_text(encoding="utf-8")
    locales = re.findall(
        r"^  (en|zh): \{\s*translation: \{(.*?)^    \},\s*^  \},",
        text,
        re.S | re.M,
    )
    assert {name for name, _ in locales} == {"en", "zh"}, "en/zh blocks not found"
    return {name: _parse_locale(body) for name, body in locales}


def test_en_zh_key_sets_match() -> None:
    res = _resources()
    assert res["en"], "no keys parsed from i18n.ts"
    assert set(res["en"]) == set(res["zh"])


def test_every_t_usage_is_defined() -> None:
    keys = set(_resources()["en"])
    used: set[str] = set()
    for tsx in SRC.glob("*.tsx"):
        used |= set(re.findall(r"\bt\('(\w+)'", tsx.read_text(encoding="utf-8")))
    assert used, "no t() usages found — glob broken?"
    missing = used - keys
    assert not missing, f"t() keys missing from i18n.ts: {sorted(missing)}"


def test_ported_keys_match_legacy_verbatim() -> None:
    res = _resources()
    problems: list[str] = []
    for react_key, legacy_key in LEGACY_MAP.items():
        for lang in ("en", "zh"):
            expected = _I18N[lang][legacy_key]
            if react_key == "newChat":  # "+" lives on the button glyph
                expected = expected.lstrip("+ ")
            got = res[lang].get(react_key)
            if got != expected:
                problems.append(f"{lang}.{react_key}: {got!r} != legacy {expected!r}")
    assert not problems, "\n".join(problems)
