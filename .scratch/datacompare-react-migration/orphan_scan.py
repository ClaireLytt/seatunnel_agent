"""Scan for unreferenced top-level symbols in the ui_* REST helper modules.

Evidence generator for ticket 11 (grep-equivalent): a symbol counts as
referenced if its name appears anywhere in src/ or tests/ outside its own
defining module.
"""
import ast
import pathlib
import re

BASE = pathlib.Path(__file__).resolve().parents[2]
PKG = BASE / "src/seatunnel_agent/agents/data/data_comparison"
FILES = list((BASE / "src").rglob("*.py")) + list((BASE / "tests").rglob("*.py"))
CORPUS = {f: f.read_text(encoding="utf-8") for f in FILES}

for mod in ("ui_shared.py", "ui_cards.py", "ui_reports.py"):
    p = PKG / mod
    tree = ast.parse(CORPUS[p])
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            names += [t.id for t in node.targets if isinstance(t, ast.Name)]
    print(f"== {mod} ==")
    for n in sorted(set(names)):
        pat = re.compile(rf"\b{re.escape(n)}\b")
        refs = [str(f.relative_to(BASE)) for f, s in CORPUS.items()
                if f != p and pat.search(s)]
        if not refs:
            print(f"  ORPHAN {n}")
        else:
            print(f"  used   {n}: {len(refs)} file(s): "
                  + ", ".join(sorted(refs)[:4]))
