"""Seed the Hive test tables for the UI hive suite (idempotent).

Executes examples/dc_hive_test_data.sql statement by statement via pyhive:
DROP + CREATE + INSERT for every dc_test_* table, so each run rebuilds the
exact fixtures the hive-tagged cases assert against.

Usage:
    python scripts/seed_hive.py [--host H] [--port P] [--database DB] [--dry-run]

Defaults come from HIVE_HOST / HIVE_PORT / HIVE_DATABASE (a .env in the
working directory is honored).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

SQL_FILE = Path(__file__).resolve().parent.parent / "examples" / "dc_hive_test_data.sql"


def statements(text: str) -> list[str]:
    # strip line comments, then split on ';' — the fixture file contains no
    # string literals with semicolons or dashes, by construction
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("--")]
    joined = "\n".join(lines)
    return [s.strip() for s in joined.split(";") if s.strip()]


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.getenv("HIVE_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.getenv("HIVE_PORT", "10000")))
    ap.add_argument("--database", default=os.getenv("HIVE_DATABASE", "default"))
    ap.add_argument("--dry-run", action="store_true",
                    help="print the parsed statements without executing")
    args = ap.parse_args()

    stmts = statements(SQL_FILE.read_text(encoding="utf-8"))
    print(f"{len(stmts)} statements parsed from {SQL_FILE.name}")
    if args.dry_run:
        for s in stmts:
            print(re.sub(r"\s+", " ", s)[:100])
        return 0

    from pyhive import hive
    conn = hive.Connection(host=args.host, port=args.port,
                           database=args.database)
    cursor = conn.cursor()
    t0 = time.time()
    try:
        for i, s in enumerate(stmts, 1):
            head = re.sub(r"\s+", " ", s)[:70]
            print(f"[{i}/{len(stmts)}] {head}", flush=True)
            cursor.execute(s)
    finally:
        cursor.close()
        conn.close()
    print(f"seeded in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
