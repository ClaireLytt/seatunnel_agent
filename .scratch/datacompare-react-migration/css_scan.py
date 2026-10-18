"""List every st-* class selector in hub/css.py with its reference count in
src/**.py (excluding css.py) — evidence for the ticket-11 CSS prune."""
import pathlib
import re

BASE = pathlib.Path(".")
css = (BASE / "src/seatunnel_agent/hub/css.py").read_text(encoding="utf-8")
classes = sorted(set(re.findall(r"\.(st-[a-z0-9-]+)", css)))
files = [f for f in (BASE / "src").rglob("*.py")
         if f.name != "css.py" and "__pycache__" not in str(f)]
corpus = {f: f.read_text(encoding="utf-8") for f in files}
for c in classes:
    refs = [str(f.relative_to(BASE)) for f, t in corpus.items() if c in t]
    mark = "ORPHAN" if not refs else "used  "
    print(f"{mark} {c}: " + ", ".join(sorted(refs)[:5]))
