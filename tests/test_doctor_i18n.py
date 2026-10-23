"""i18n parity for the React /doctor workspace.

Checks frontend/doctor/src/i18n.ts:
- en and zh expose identical key sets;
- every t('key') used in .tsx files is defined.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import i18n_resources

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "doctor" / "src"
I18N_TS = SRC / "i18n.ts"


def test_en_zh_key_sets_match() -> None:
    res = i18n_resources(I18N_TS)
    assert res["en"], "no keys parsed from i18n.ts"
    assert set(res["en"]) == set(res["zh"])


def test_every_t_usage_is_defined() -> None:
    keys = set(i18n_resources(I18N_TS)["en"])
    used: set[str] = set()
    for tsx in SRC.glob("*.tsx"):
        used |= set(re.findall(r"\bt\('(\w+)'", tsx.read_text(encoding="utf-8")))
    assert used, "no t() usages found — glob broken?"
    missing = used - keys
    assert not missing, f"t() keys missing from i18n.ts: {sorted(missing)}"
