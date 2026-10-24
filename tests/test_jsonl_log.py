"""JsonlLog behavior: tail reads, where-filter semantics, corrupt lines.

Seam: the shared append/rotate/tail-read store every query/audit log uses.
Added with the reversed early-stop read so the filter path's contract
(last *n* matching records, in file order) is pinned before optimizing.
"""

from __future__ import annotations

from seatunnel_agent.common.jsonl_log import JsonlLog


def _make(tmp_path, records):
    log = JsonlLog(tmp_path / "x.jsonl")
    for rec in records:
        log.append(rec)
    return log


def test_recent_returns_tail_in_order(tmp_path):
    log = _make(tmp_path, [{"i": i} for i in range(10)])
    assert [r["i"] for r in log.recent(3)] == [7, 8, 9]


def test_recent_where_returns_last_n_matching_in_order(tmp_path):
    log = _make(tmp_path, [{"i": i, "kind": "a" if i % 2 else "b"}
                           for i in range(20)])
    out = log.recent(3, where=lambda r: r["kind"] == "a")
    assert [r["i"] for r in out] == [15, 17, 19]


def test_recent_skips_corrupt_lines(tmp_path):
    log = _make(tmp_path, [{"i": 1}, {"i": 2}])
    with open(log.path, "a", encoding="utf-8") as f:
        f.write("not json\n")
    log.append({"i": 3})
    assert [r["i"] for r in log.recent(5)] == [1, 2, 3]


def test_recent_missing_file(tmp_path):
    assert JsonlLog(tmp_path / "absent.jsonl").recent(5) == []
