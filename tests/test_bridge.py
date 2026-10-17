"""localStorage bridge keys: Python and React definitions stay in sync."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.common.bridge import DATASKEW_SQL_KEY, TRANSPILE_SQL_KEY

TS_FILE = Path("frontend") / "shared" / "src" / "bridge.ts"


def test_bridge_keys_match_frontend():
    ts = TS_FILE.read_text(encoding="utf-8")
    assert f"TRANSPILE_SQL_KEY = '{TRANSPILE_SQL_KEY}'" in ts
    assert f"DATASKEW_SQL_KEY = '{DATASKEW_SQL_KEY}'" in ts


def test_no_bare_bridge_keys_left():
    # every usage goes through the constants; no stray literals in src/
    src = Path("src")
    offenders = []
    for p in src.rglob("*.py"):
        if p.name == "bridge.py":
            continue
        text = p.read_text(encoding="utf-8")
        if "st_transpile_sql" in text or "st_dataskew_sql" in text:
            offenders.append(str(p))
    assert not offenders, offenders
