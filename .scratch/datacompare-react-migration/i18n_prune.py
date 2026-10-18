"""Prune dead DC_I18N keys (grep-proven unreferenced in src/frontend) and
drop them from the test census enumerations."""
import pathlib
import re

keys = [k.strip() for k in pathlib.Path(
    ".scratch/datacompare-react-migration/prune_keys.txt"
).read_text().split() if k.strip()]

i18n = pathlib.Path("src/seatunnel_agent/agents/data/data_comparison/i18n.py")
src = i18n.read_text(encoding="utf-8")
removed = 0
for k in keys:
    # single-line entries:  "key": "value",   (value may contain escapes)
    pat = re.compile(rf'^[ \t]+"{re.escape(k)}":.*\n', re.M)
    n = len(pat.findall(src))
    assert n == 2, f"{k}: expected 2 occurrences (en+zh), got {n}"
    src = pat.sub("", src)
    removed += n
i18n.write_text(src, encoding="utf-8")
print(f"i18n.py: removed {removed} lines for {len(keys)} keys")

# test census lists: drop pruned key strings from enumerations
tp = pathlib.Path("tests/test_data_comparison.py")
t = tp.read_text(encoding="utf-8")
for k in keys:
    t = re.sub(rf'"{re.escape(k)}",?\s*', "", t)
tp.write_text(t, encoding="utf-8")
print("tests updated")
