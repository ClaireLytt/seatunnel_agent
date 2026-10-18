"""Reference scan for DC_I18N keys: key -> src files (excl. i18n.py) and tests."""
import pathlib
import re
import sys

sys.path.insert(0, "src")
from seatunnel_agent.agents.data.data_comparison.i18n import DC_I18N  # noqa: E402

BASE = pathlib.Path(".")
src_files = [f for f in (BASE / "src").rglob("*.py")
             if f.name != "i18n.py" and "__pycache__" not in str(f)]
test_files = [f for f in (BASE / "tests").rglob("*.py")]
src_corpus = {f: f.read_text(encoding="utf-8") for f in src_files}
test_corpus = {f: f.read_text(encoding="utf-8") for f in test_files}
# frontend locales may embed the same keys
fe = [f for f in (BASE / "frontend" / "data_comparison" / "src").rglob("*")
      if f.is_file() and f.suffix in (".ts", ".tsx", ".json")]
fe_corpus = {f: f.read_text(encoding="utf-8") for f in fe}

dead = []
test_only = []
for key in sorted(DC_I18N["en"]):
    pat = re.compile(rf"[\"']{re.escape(key)}[\"']")
    s = [str(f) for f, t in src_corpus.items() if pat.search(t)]
    te = [str(f) for f, t in test_corpus.items() if pat.search(t)]
    f_ = [str(f) for f, t in fe_corpus.items() if pat.search(t)]
    if not s and not te and not f_:
        dead.append(key)
    elif not s and te:
        test_only.append((key, te))

print(f"total keys: {len(DC_I18N['en'])}")
print(f"DEAD (no refs anywhere): {len(dead)}")
for k in dead:
    print("  ", k)
print(f"TEST-ONLY: {len(test_only)}")
for k, te in test_only:
    print("  ", k, "->", ", ".join(sorted(set(te))))
# dynamic dc( f-string usage check
dyn = []
for f, t in list(src_corpus.items()) + list(test_corpus.items()):
    for m in re.finditer(r"dc\(\s*f[\"']([^\"']+)[\"']", t):
        dyn.append((str(f), m.group(1)))
print("DYNAMIC dc(f'...') usages:")
for f, p in dyn:
    print("  ", f, p)
