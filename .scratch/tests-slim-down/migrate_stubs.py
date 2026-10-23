"""Ticket 03 migration: delete local _text/_tool/_run_cli copies, alias to
the shared conftest helpers so call sites stay untouched."""
from __future__ import annotations

import re
import sys
from pathlib import Path

# a def block = header + every following line that is blank or indented
DEFS = re.compile(
    r"\ndef _(text|tool|run_cli)\([^\n]*\n"
    r"(?:[ \t]+[^\n]*\n|\n(?=[ \t\n]*[ \t]\S))*",
)


def migrate(path: Path) -> str:
    text = orig = path.read_text(encoding="utf-8")
    names = DEFS.findall(text)
    if not names:
        return "nothing to do"
    text = DEFS.sub("\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    imports, aliases = [], []
    if "text" in names or "tool" in names:
        imports.append("llm_text, llm_tool")
        aliases += ["_text = llm_text", "_tool = llm_tool"]
    if "run_cli" in names:
        imports.append("run_cli")
        aliases.append("_run_cli = run_cli")
    imp = "from tests.conftest import " + ", ".join(imports)
    m = list(re.finditer(r"^(?:import|from) [^\n]+\n", text, re.M))[-1]
    block = "\n" + imp + "\n\n" + "\n".join(aliases) + "\n"
    text = text[: m.end()] + block + text[m.end():]
    if text != orig:
        path.write_text(text, encoding="utf-8")
    return f"migrated: {names}"


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(f"{Path(arg).name}: {migrate(Path(arg))}")
