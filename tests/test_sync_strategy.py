"""Deterministic core tests for the sync-strategy agent."""

from __future__ import annotations

from pathlib import Path

import pytest

from seatunnel_agent.agents.data.sync_strategy import (
    parse_tables,
    recommend,
    render_markdown,
)
from seatunnel_agent.agents.data.sync_strategy.tools import sync_strategy

DEMO = (Path(__file__).resolve().parents[1] / "examples"
        / "syncstrategy_demo" / "tables.json").read_text(encoding="utf-8")


def _rec():
    report = recommend(parse_tables(DEMO))
    return {r.table: r for r in report.recommendations}


def test_demo_recommendations():
    by = _rec()
    # minute latency + binlog → CDC
    assert by["ods.orders"].strategy == "cdc"
    assert by["ods.orders"].reasons == ["latency_needs_cdc"]
    # update ts + pk, big, low churn → timestamp incremental with upsert
    assert by["ods.users"].strategy == "incr_timestamp"
    assert "pk_upsert" in by["ods.users"].reasons
    assert "late_update_window" in by["ods.users"].risks
    # small dict table with deletes → full
    assert by["ods.dict_region"].strategy == "full"
    assert by["ods.dict_region"].reasons == ["deletes_without_cdc"]
    # append-only event log, pk only → pk incremental
    assert by["ods.events"].strategy == "incr_pk"
    assert "pk_incr_misses_updates" in by["ods.events"].risks
    # deletes, no cdc, big → full with load warning
    assert by["ods.inventory"].strategy == "full"
    assert "full_on_big_table" in by["ods.inventory"].risks


def test_high_churn_prefers_full():
    tables = parse_tables(
        '[{"table":"t","rows":10000000,"daily_change_rows":5000000,'
        '"has_update_ts":true,"has_pk":true}]')
    rec = recommend(tables).recommendations[0]
    assert rec.strategy == "full"
    assert rec.reasons == ["high_churn"]


def test_urgent_latency_without_cdc_flags_risk():
    tables = parse_tables(
        '[{"table":"t","rows":10000000,"daily_change_rows":1000,'
        '"has_update_ts":true,"has_pk":true,"latency":"realtime"}]')
    rec = recommend(tables).recommendations[0]
    assert rec.strategy == "incr_timestamp"
    assert "latency_without_cdc" in rec.risks


def test_csv_input_and_bool_coercion():
    csv_text = ("table,rows,daily_change_rows,has_update_ts,has_pk,"
                "has_deletes,cdc_available,latency\n"
                "ods.a,2000000,1000,yes,true,no,0,daily\n")
    rec = recommend(parse_tables(csv_text)).recommendations[0]
    assert rec.strategy == "incr_timestamp"


def test_bad_inputs():
    with pytest.raises(ValueError):
        parse_tables("")
    with pytest.raises(ValueError, match="missing 'table'"):
        parse_tables('[{"rows": 1}]')
    with pytest.raises(ValueError, match="latency"):
        parse_tables('[{"table":"t","latency":"asap"}]')
    with pytest.raises(ValueError, match="tables"):
        parse_tables('{"nope": []}')


def test_inventory_from_ddl():
    ddl = """
    -- user dimension
    CREATE TABLE IF NOT EXISTS ods.users (
      user_id BIGINT PRIMARY KEY,
      user_name VARCHAR(64),
      updated_at TIMESTAMP
    ) ENGINE=InnoDB;

    CREATE TABLE ods.events (
      event_id BIGINT,
      payload TEXT,
      PRIMARY KEY (event_id)
    );
    """
    tables = parse_tables(ddl)
    by = {t.table: t for t in tables}
    users = by["ods.users"]
    assert users.has_pk and users.pk_col == "user_id"
    assert users.has_update_ts and users.update_ts_col == "updated_at"
    events = by["ods.events"]
    assert events.has_pk and events.pk_col == "event_id"
    assert not events.has_update_ts
    # recommendations run off schema facts: ts → incr_timestamp, pk → incr_pk
    recs = {r.table: r for r in recommend(tables).recommendations}
    assert recs["ods.users"].strategy == "incr_timestamp"
    assert recs["ods.events"].strategy == "incr_pk"
    assert "WHERE updated_at >= '${watermark}'" in recs["ods.users"].config


def test_ddl_without_create_table_rejected():
    with pytest.raises(ValueError, match="no CREATE TABLE"):
        parse_tables("CREATE TABLE broken")


def test_config_stubs_follow_strategy():
    by = _rec()
    # cdc → streaming MySQL-CDC source with the real table name
    orders = by["ods.orders"].config
    assert 'job.mode = "STREAMING"' in orders
    assert 'table-names = ["ods.orders"]' in orders
    # timestamp incremental → watermark-bounded query with the real column
    users = by["ods.users"].config
    assert 'job.mode = "BATCH"' in users
    assert "WHERE modified_time >= '${watermark}'" in users
    # pk incremental → last_max_pk bound (placeholder when col unknown)
    events = by["ods.events"].config
    assert "WHERE <pk_col> > ${last_max_pk}" in events
    # full → plain bounded-by-nothing query, batch mode
    assert "SELECT * FROM ods.dict_region" in by["ods.dict_region"].config
    # every stub keeps the sink as an explicit TODO
    assert all("sink {" in r.config for r in by.values())


def test_rows_moved_estimate():
    by = _rec()
    # incremental moves only the churn; the saving is quantified
    users = by["ods.users"]
    assert users.rows_per_sync == 40000
    assert users.saving_ratio == pytest.approx(1 - 40000 / 3000000, abs=1e-4)
    # full reload moves everything, no saving ratio shown
    assert by["ods.inventory"].rows_per_sync == 20000000
    md = render_markdown(recommend(parse_tables(DEMO)), lang="en")
    assert "saves 98.7% vs full" in md  # ods.users
    # unknown row counts render as '-'
    unknown = recommend(parse_tables('[{"table":"t","has_pk":true}]'))
    assert unknown.recommendations[0].rows_per_sync == -1
    assert "| - |" in render_markdown(unknown, lang="en")


def test_schedule_suggestions():
    by = _rec()
    assert by["ods.orders"].schedule == "streaming"      # cdc
    assert by["ods.users"].schedule == "0 * * * *"       # hours latency
    assert by["ods.events"].schedule == "30 2 * * *"     # daily
    md = render_markdown(recommend(parse_tables(DEMO)), lang="zh")
    assert "常驻流作业" in md and "`0 * * * *`" in md


def test_report_includes_config_section():
    report = recommend(parse_tables(DEMO))
    zh = render_markdown(report, lang="zh")
    assert "SeaTunnel 作业配置骨架" in zh
    assert "```hocon" in zh


def test_report_zh_en_and_tool():
    report = recommend(parse_tables(DEMO))
    zh = render_markdown(report, lang="zh")
    en = render_markdown(report, lang="en")
    assert "增量同步策略推荐" in zh and "时间戳增量" in zh
    assert "Sync Strategy Recommendation" in en and "CDC" in en
    md = sync_strategy(DEMO, lang="en")
    assert "full reload" in md
    assert "must not be empty" in sync_strategy(" ")
    assert "bad input" in sync_strategy("{broken")
