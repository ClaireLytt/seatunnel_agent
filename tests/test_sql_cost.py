"""Deterministic core tests for the SQL cost estimator."""

from __future__ import annotations

from pathlib import Path

import pytest

from seatunnel_agent.agents.data.sql_cost import (
    estimate,
    parse_stats,
    render_markdown,
)
from seatunnel_agent.agents.data.sql_cost.estimator import (
    AGG_SHRINK,
    CORE_THROUGHPUT,
)
from seatunnel_agent.agents.data.sql_cost.tools import sql_cost

DEMO_DIR = Path(__file__).resolve().parents[1] / "examples" / "sqlcost_demo"
SQL = (DEMO_DIR / "query.sql").read_text(encoding="utf-8")
STATS = (DEMO_DIR / "stats.json").read_text(encoding="utf-8")


def _card():
    return estimate(SQL, parse_stats(STATS))


def test_scan_discounts():
    card = _card()
    by = {s.table: s for s in card.scans}
    orders = by["ods.orders"]
    assert orders.pruned is True
    # 100 GiB / 365 partitions * physical read set {amount,dt,user_id}/20
    assert orders.bytes == pytest.approx(
        107374182400 / 365 * (3 / 20), rel=1e-6)
    assert orders.rows == pytest.approx(500000000 / 365, rel=1e-6)
    users = by["ods.users"]
    assert users.pruned is False
    assert users.col_ratio == pytest.approx(2 / 10)  # {region, user_id}


def test_shuffle_and_output_model():
    card = _card()
    assert card.joins == 1 and card.aggregates is True
    sides = sorted(s.bytes for s in card.scans)
    # users side (~100 MB after column pruning) exceeds the broadcast
    # threshold → both sides shuffle, plus one aggregation exchange
    assert card.broadcast_joins == 0
    assert card.shuffle_bytes == pytest.approx(
        sides[0] + sides[1] + card.scan_bytes, rel=1e-6)
    assert card.output_rows == pytest.approx(
        max(s.rows for s in card.scans) / AGG_SHRINK, rel=1e-6)
    assert card.core_seconds == pytest.approx(
        (card.scan_bytes + card.shuffle_bytes) / CORE_THROUGHPUT, rel=1e-6)
    lo, hi = card.wall_seconds
    assert hi == pytest.approx(lo * 4, rel=1e-6)  # 0.5x vs 2x band


def test_broadcast_when_small_side_fits():
    stats = parse_stats(
        '[{"table":"big","rows":1000000,"bytes":10737418240},'
        ' {"table":"small","rows":1000,"bytes":1048576}]')
    card = estimate(
        "SELECT * FROM big b JOIN small s ON b.k = s.k", stats)
    assert card.broadcast_joins == 1
    assert card.shuffle_bytes == 0.0  # no agg, broadcast join


def test_missing_table_reported_not_guessed():
    card = estimate("SELECT * FROM nowhere.t WHERE x = 1",
                    parse_stats(STATS))
    assert card.missing == ["nowhere.t"]
    assert card.scan_bytes == 0.0


def test_bad_inputs():
    with pytest.raises(ValueError, match="empty SQL"):
        estimate("  ", parse_stats(STATS))
    with pytest.raises(ValueError, match="empty stats"):
        parse_stats(" ")
    with pytest.raises(ValueError, match="missing 'table'"):
        parse_stats('[{"rows": 1}]')
    with pytest.raises(ValueError, match="not parseable"):
        estimate("THIS IS NOT SQL !!", parse_stats(STATS))


def test_report_zh_en_and_tool():
    card = _card()
    zh = render_markdown(card, lang="zh")
    en = render_markdown(card, lang="en")
    assert "SQL 代价卡" in zh and "假设" in zh and "建议并行度" in zh
    assert "SQL Cost Card" in en and "Assumptions" in en
    assert "ods.orders" in en
    md = sql_cost(SQL, STATS, lang="en")
    assert "core-seconds" in md
    assert "must not be empty" in sql_cost(" ", STATS)
    assert "must not be empty" in sql_cost(SQL, " ")


def test_api_what_if_assume_partitions():
    """API assume_partitions appends the what-if delta; bad specs 400."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.sql_cost import api as sc_api

    root = Path(__file__).resolve().parents[1] / "examples" / "sqlcost_demo"
    sql = (root / "query.sql").read_text("utf-8")
    stats = (root / "stats.json").read_text("utf-8")
    app = FastAPI()
    app.include_router(sc_api.router)
    client = TestClient(app)
    res = client.post("/api/sqlcost/estimate", json={
        "sql": sql, "stats_text": stats, "report": True, "lang": "en",
        "assume_partitions": ["ods.users:user_id:10"]})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["what_if"]["scan_saved_pct"] > 0
    assert "What-if" in body["report"]
    # malformed spec and unknown partition count are 400s, not guesses
    for bad in ("nope", "ods.users:user_id"):
        res = client.post("/api/sqlcost/estimate", json={
            "sql": sql, "stats_text": stats, "assume_partitions": [bad]})
        assert res.status_code == 400
