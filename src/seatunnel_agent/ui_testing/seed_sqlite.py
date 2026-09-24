"""Seed the SQLite demo database with the ``dc_test_*`` tables.

Row data is defined here as constants and mirrors
``examples/dc_hive_test_data.sql`` exactly (a unit test parses the SQL file
and asserts both stay in sync).  Type mapping: INT->INTEGER, STRING->TEXT,
DOUBLE/DECIMAL->REAL.  Hive partition columns become plain columns.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB = "config/uitest_demo.db"

# (table, columns-DDL, rows)
SEED: list[tuple[str, str, list[tuple]]] = [
    (
        "dc_test_orders_a",
        "id INTEGER, order_no TEXT, category TEXT, amount REAL, status TEXT,"
        " phone TEXT, email TEXT, id_card TEXT, update_time TEXT",
        [
            (1,  "ORD001", "electronics", 100.00, "paid",      "13800000001", "u1@test.com",  "110101199001011234", "2024-06-01 10:00:00"),
            (2,  "ORD002", "clothing",    220.50, "paid",      "13800000002", "u2@test.com",  "110101199002021234", "2024-06-01 11:00:00"),
            (3,  "ORD003", "electronics", 300.00, "paid",      "13800000003", "u3@test.com",  "110101199003031234", "2024-06-02 09:30:00"),
            (4,  "ORD004", "food",         45.90, "shipped",   "13800000004", "u4@test.com",  "110101199004041234", "2024-06-02 14:00:00"),
            (5,  "ORD005", "clothing",    180.00, "paid",      "13800000005", "u5@test.com",  "110101199005051234", "2024-06-03 08:15:00"),
            (6,  "ORD006", "food",         62.30, "cancelled", "13800000006", "u6@test.com",  "110101199006061234", "2024-06-03 16:45:00"),
            (7,  "ORD007", "electronics", 999.99, "paid",      "13800000007", "u7@test.com",  "110101199007071234", "2024-06-04 10:20:00"),
            (8,  "ORD008", "books",        35.00, "shipped",   "13800000008", "u8@test.com",  "110101199008081234", "2024-06-04 18:00:00"),
            (9,  "ORD009", "books",        58.80, "paid",      "13800000009", "u9@test.com",  "110101199009091234", "2024-06-05 09:00:00"),
            (10, "ORD010", "food",        120.00, "paid",      "13800000010", "u10@test.com", "110101199010101234", "2024-06-05 12:00:00"),
        ],
    ),
    (
        "dc_test_orders_b",
        "id INTEGER, order_no TEXT, category TEXT, amount REAL, status TEXT,"
        " phone TEXT, email TEXT, id_card TEXT, update_time TEXT",
        [
            (1,  "ORD001", "electronics",  100.00, "paid",      "13800000001", "u1@test.com",  "110101199001011234", "2024-06-01 10:00:00"),
            (2,  "ORD002", "clothing",     220.50, "paid",      "13800000002", "u2@test.com",  "110101199002021234", "2024-06-01 11:00:00"),
            (3,  "ORD003", "electronics",  350.00, "paid",      "13800000003", "u3@test.com",  "110101199003031234", "2024-06-06 10:00:00"),
            (4,  "ORD004", "food",          45.90, "shipped",   "13800000004", "u4@test.com",  "110101199004041234", "2024-06-02 14:00:00"),
            (5,  "ORD005", "clothing",     180.00, "refund",    "13800000005", "u5@test.com",  "110101199005051234", "2024-06-06 11:00:00"),
            (6,  "ORD006", "food",          62.30, "cancelled", "13800000006", "u6@test.com",  "110101199006061234", "2024-06-03 16:45:00"),
            (7,  "ORD007", "electronics",  999.99, "paid",      "13800000007", None,           "110101199007071234", "2024-06-04 10:20:00"),
            (8,  "ORD008", "books",         35.00, "shipped",   "13800000008", None,           "110101199008081234", "2024-06-04 18:00:00"),
            (11, "ORD011", "electronics", 1500.00, "paid",      "13800000011", "u11@test.com", "110101199011111234", "2024-06-06 12:00:00"),
        ],
    ),
    (
        "dc_test_schema_a",
        "id INTEGER, name TEXT, amount REAL, created TEXT",
        [
            (1, "alice", 10.50, "2024-06-01"),
            (2, "bob",   20.00, "2024-06-01"),
            (3, "carol", 30.25, "2024-06-02"),
        ],
    ),
    (
        "dc_test_schema_b",
        "id INTEGER, user_name TEXT, amount REAL, remark TEXT, created TEXT",
        [
            (1, "alice", 10.50, "ok",    "2024-06-01"),
            (2, "bob",   21.00, "check", "2024-06-01"),
            (3, "carol", 30.25, "",      "2024-06-02"),
        ],
    ),
    (
        "dc_test_metrics_a",
        "id INTEGER, region TEXT, sales REAL, qty INTEGER",
        [
            (1,  "north", 10.0,  2), (2,  "north", 20.0,  3), (3,  "north", 30.0,  4),
            (4,  "north", 40.0,  5), (5,  "north", 50.0,  1), (6,  "north", 60.0,  2),
            (7,  "north", 70.0,  3), (8,  "north", 80.0,  4), (9,  "north", 90.0,  5),
            (10, "north", 100.0, 1), (11, "north", 110.0, 2), (12, "north", 120.0, 3),
            (13, "north", 130.0, 4), (14, "north", 140.0, 5), (15, "north", 150.0, 1),
            (16, "north", 160.0, 2), (17, "south", 170.0, 3), (18, "south", 180.0, 4),
            (19, "east",  190.0, 5), (20, "west",  200.0, 1),
        ],
    ),
    (
        "dc_test_metrics_b",
        "id INTEGER, region TEXT, sales REAL, qty INTEGER",
        [
            (1,  "north", 10.0,  2), (2,  "north", 20.0,  3), (3,  "north", 30.0,  4),
            (4,  "north", 44.0,  5), (5,  "north", 50.0,  1), (6,  "south", 60.0,  2),
            (7,  "south", 70.0,  3), (8,  "south", 80.0,  4), (9,  "south", 90.0,  5),
            (10, "south", 100.0, 1), (11, "east",  110.0, 2), (12, "east",  120.0, 3),
            (13, "east",  130.0, 4), (14, "east",  140.0, 5), (15, "east",  155.0, 1),
            (16, "west",  160.0, 2), (17, "west",  170.0, 3), (18, "west",  180.0, 4),
            (19, "west",  190.0, 5), (20, "west",  200.0, 1),
        ],
    ),
    (
        # Hive partition column dt becomes a plain column in SQLite.
        "dc_test_part_a",
        "id INTEGER, val REAL, dt TEXT",
        [
            (1, 1.1, "2024-06-01"), (2, 2.2, "2024-06-01"), (3, 3.3, "2024-06-01"),
            (4, 4.4, "2024-06-01"), (5, 5.5, "2024-06-01"),
            (6, 6.6, "2024-06-02"), (7, 7.7, "2024-06-02"), (8, 8.8, "2024-06-02"),
            (9, 9.9, "2024-06-02"), (10, 10.1, "2024-06-02"),
            (11, 11.1, "2024-06-03"), (12, 12.2, "2024-06-03"), (13, 13.3, "2024-06-03"),
            (14, 14.4, "2024-06-03"), (15, 15.5, "2024-06-03"),
        ],
    ),
    (
        "dc_test_part_b",
        "id INTEGER, val REAL, dt TEXT",
        [
            (1, 1.1, "2024-06-01"), (2, 2.2, "2024-06-01"), (3, 3.3, "2024-06-01"),
            (4, 4.4, "2024-06-01"), (5, 5.5, "2024-06-01"),
            (6, 6.6, "2024-06-02"), (7, 7.7, "2024-06-02"), (8, 8.8, "2024-06-02"),
        ],
    ),
    (
        "dc_test_same_a",
        "id INTEGER, name TEXT, score REAL",
        [
            (1, "aa", 90.5), (2, "bb", 80.0), (3, "cc", 70.5),
            (4, "dd", 60.0), (5, "ee", 95.0),
        ],
    ),
    (
        "dc_test_same_b",
        "id INTEGER, name TEXT, score REAL",
        [
            (1, "aa", 90.5), (2, "bb", 80.0), (3, "cc", 70.5),
            (4, "dd", 60.0), (5, "ee", 95.0),
        ],
    ),
]


def seed_sqlite(db_path: str | Path = DEFAULT_DB) -> Path:
    """(Re)create every ``dc_test_*`` table in *db_path*.  Idempotent."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        for table, ddl, rows in SEED:
            cur.execute(f"DROP TABLE IF EXISTS {table}")
            cur.execute(f"CREATE TABLE {table} ({ddl})")
            if rows:
                marks = ", ".join("?" * len(rows[0]))
                cur.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)
        conn.commit()
    finally:
        conn.close()
    return path


def cleanup_sqlite(db_path: str | Path = DEFAULT_DB) -> None:
    """Drop only the ``dc_test_*`` tables (never touches anything else)."""
    path = Path(db_path)
    if not path.is_file():
        return
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        names = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name LIKE 'dc_test_%'")]
        for n in names:
            cur.execute(f"DROP TABLE IF EXISTS {n}")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    p = seed_sqlite()
    print(f"Seeded {len(SEED)} tables into {p}")
