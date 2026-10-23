"""One-shot migration: point test_*_i18n.py files at the shared conftest
i18n helpers and delete their local copies. Idempotent; prints a summary."""
from __future__ import annotations

import re
import sys
from pathlib import Path

HELPER_DEF = re.compile(
    r"\ndef _(parse_locale|resources|workspace_sources)\([^\n]*\n"
    r"(?:(?:    [^\n]*)?\n)*?"   # indented body lines / blank lines
    r"    return [^\n]+\n",
)

IMPORT_LINE = ("from tests.conftest import "
               "i18n_resources, workspace_sources\n")


def migrate(path: Path) -> str:
    text = orig = path.read_text(encoding="utf-8")
    hits = HELPER_DEF.findall(text)
    if not hits and "i18n_resources(" in text:
        return "already migrated"
    text = HELPER_DEF.sub("\n", text)
    # collapse the leftover blank-line runs the deletions create
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = text.replace("_resources()", "i18n_resources(I18N_TS)")
    text = text.replace("_workspace_sources()", "workspace_sources(SRC)")
    # drop direct _parse_locale calls' name if any slipped through
    assert "_parse_locale" not in text, f"{path}: stray _parse_locale use"
    if "from tests.conftest import" not in text:
        # insert after the last top-level import line
        m = list(re.finditer(r"^(?:import|from) [^\n]+\n", text, re.M))[-1]
        text = text[: m.end()] + "\n" + IMPORT_LINE + text[m.end():]
    if "workspace_sources(SRC)" not in text:
        text = text.replace(IMPORT_LINE,
                            "from tests.conftest import i18n_resources\n")
    if text != orig:
        path.write_text(text, encoding="utf-8")
        return f"migrated ({len(hits)} helpers removed)"
    return "no change"


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        p = Path(arg)
        print(f"{p.name}: {migrate(p)}")
