"""i18n parity for the React /depcheck workspace.

Checks frontend/dep_check/src/i18n.ts:
- en and zh expose identical key sets;
- every t('key') used in .tsx files is defined.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "dep_check" / "src"
I18N_TS = SRC / "i18n.ts"


def _parse_locale(block: str) -> dict[str, str]:
    """Extract top-level translation keys from an i18n block.

    Matches lines like ``key: 'value',`` or ``key:\\n  'val1' +\\n  'val2',``
    anchored at 6-space indent (translation object body).
    """
    result: dict[str, str] = {}
    # Match key: (possibly multi-line concatenated strings ending with ,)
    for m in re.finditer(
        r"^ {6}(\w+):\s*\n?\s*((?:'(?:[^'\\]|\\.)*'\s*\+?\s*)+),",
        block,
        re.M,
    ):
        key = m.group(1)
        raw = m.group(2)
        parts = re.findall(r"'((?:[^'\\]|\\.)*)'", raw)
        result[key] = "".join(parts).replace("\\'", "'").replace("\\n", "\n")
    return result


def _resources() -> dict[str, dict[str, str]]:
    text = I18N_TS.read_text(encoding="utf-8")
    locales = re.findall(
        r"(en|zh): \{\s*translation: \{(.*?)\},\s*\},",
        text,
        re.S,
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
