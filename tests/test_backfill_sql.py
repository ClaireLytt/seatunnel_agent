"""Deterministic core tests for the backfill SQL agent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from seatunnel_agent.agents.data.backfill_sql import (
    generate,
    parse_spec,
    render_markdown,
)
from seatunnel_agent.agents.data.backfill_sql.tools import backfill_sql

DEMO = (Path(__file__).resolve().parents[1] / "examples" / "backfillsql_demo"
        / "spec.json").read_text(encoding="utf-8")


def _spec(**over):
    data = json.loads(DEMO)
    data.update(over)
    return parse_spec(json.dumps(data))


def test_hive_overwrite_one_partition_per_date():
    result = generate(parse_spec(DEMO))
    assert [d.date for d in result.dates] == [
        "2024-05-01", "2024-05-02", "2024-05-03"]
    stmt = result.dates[0].statements
    assert len(stmt) == 1
    assert stmt[0].startswith(
        "INSERT OVERWRITE TABLE dws.sales PARTITION (dt = '2024-05-01')")
    assert "WHERE dt = '2024-05-01'" in stmt[0]
    assert result.warnings == []


def test_prechecks_bound_to_range():
    result = generate(parse_spec(DEMO))
    assert len(result.prechecks) == 2  # target + source_table
    assert "dt BETWEEN '2024-05-01' AND '2024-05-03'" in result.prechecks[0]
    assert "FROM ods.orders" in result.prechecks[1]


def test_compact_date_format():
    result = generate(_spec(date_format="yyyyMMdd"))
    assert result.dates[0].partition_value == "20240501"
    assert "WHERE dt = '20240501'" in result.dates[0].statements[0]


def test_mysql_overwrite_falls_back_to_delete_insert():
    result = generate(_spec(dialect="mysql"))
    stmt = result.dates[0].statements
    assert stmt[0] == "DELETE FROM dws.sales WHERE dt = '2024-05-01';"
    assert stmt[1].startswith("INSERT INTO dws.sales")
    assert result.warnings and "INSERT OVERWRITE" in result.warnings[0]


def test_merge_requires_keys_and_bounds_partition():
    with pytest.raises(ValueError, match="requires 'keys'"):
        _spec(mode="merge")
    result = generate(_spec(mode="merge", dialect="spark",
                            keys=["order_id"]))
    stmt = result.dates[0].statements[0]
    assert stmt.startswith("MERGE INTO dws.sales AS t")
    assert "ON t.order_id = s.order_id AND t.dt = '2024-05-01'" in stmt


def test_reconciliation_postcheck():
    result = generate(parse_spec(DEMO))
    assert len(result.postchecks) == 1
    post = result.postchecks[0]
    assert "FULL OUTER JOIN" in post
    assert "COALESCE(s.source_rows, -1) <> COALESCE(t.target_rows, -1)" in post
    assert "FROM ods.orders" in post and "FROM dws.sales" in post
    # no source_table → no reconciliation possible
    assert generate(_spec(source_table="")).postchecks == []
    md = render_markdown(result, lang="zh")
    assert "对账" in md


def test_hourly_grain():
    result = generate(_spec(date_format="yyyy-MM-dd HH", start="2024-05-01",
                            end="2024-05-01"))
    assert len(result.dates) == 24  # one slot per hour
    assert result.dates[0].partition_value == "2024-05-01 00"
    assert result.dates[-1].partition_value == "2024-05-01 23"
    assert result.dates[5].date == "2024-05-01T05"
    assert "WHERE dt = '2024-05-01 05'" in result.dates[5].statements[0]


def test_hourly_grain_safety():
    with pytest.raises(ValueError, match="hourly range exceeds"):
        _spec(date_format="yyyyMMddHH", start="2024-01-01", end="2024-03-01")
    with pytest.raises(ValueError, match="needs 'HH'"):
        _spec(grain="hour")
    with pytest.raises(ValueError, match="grain must be"):
        _spec(grain="minute")


def test_safety_rules():
    with pytest.raises(ValueError, match="placeholder"):
        _spec(source="SELECT * FROM ods.orders")
    with pytest.raises(ValueError, match="366 days"):
        _spec(start="2020-01-01", end="2022-01-01")
    with pytest.raises(ValueError, match="before start"):
        _spec(start="2024-05-03", end="2024-05-01")
    with pytest.raises(ValueError, match="bad identifier"):
        _spec(table="dws.sales; drop table x")
    with pytest.raises(ValueError, match="missing field"):
        parse_spec('{"table": "t"}')


def test_explicit_dates_list():
    result = generate(_spec(dates=["2024-05-03", "2024-05-01",
                                   "2024-05-01"], start="", end=""))
    # deduped, sorted, non-contiguous — only the named slots
    assert [d.date for d in result.dates] == ["2024-05-01", "2024-05-03"]
    assert "dt BETWEEN '2024-05-01' AND '2024-05-03'" in result.prechecks[0]
    with pytest.raises(ValueError, match="day grain only"):
        _spec(dates=["2024-05-01"], date_format="yyyy-MM-dd HH")
    with pytest.raises(ValueError, match="ISO dates"):
        _spec(dates=["yesterday"])


def test_specs_from_plan_bridge():
    from seatunnel_agent.agents.data.backfill_sql import specs_from_plan
    from seatunnel_agent.agents.data.backfill_sql.tools import backfill_specs

    plan = ('{"tables": ['
            '{"table": "dws.sales", "missing": ["2024-05-05"],'
            ' "cascade": ["2024-05-04"]},'
            '{"table": "ads.report", "missing": [], "cascade": []}]}')
    specs = specs_from_plan(plan)
    assert len(specs) == 1  # the empty-dates table is skipped
    spec = specs[0]
    assert spec["table"] == "dws.sales"
    assert spec["dates"] == ["2024-05-04", "2024-05-05"]
    assert "{date}" in spec["source"]
    # the emitted skeleton round-trips through the generator once filled
    import json as _json
    spec["source"] = ("SELECT * FROM ods.orders "
                      "WHERE dt = '{date}'")
    result = generate(parse_spec(_json.dumps(spec)))
    assert [d.date for d in result.dates] == ["2024-05-04", "2024-05-05"]
    md = backfill_specs(plan, lang="en")
    assert "```json" in md and "dws.sales" in md
    assert "bad input" in backfill_specs('{"tables": []}')


def test_overwrite_dynamic_single_statement():
    result = generate(_spec(
        mode="overwrite_dynamic", dialect="spark",
        source="SELECT order_id, dt FROM ods.orders "
               "WHERE dt BETWEEN '{start}' AND '{end}'"))
    assert len(result.dates) == 1
    block = result.dates[0]
    assert block.date == "2024-05-01..2024-05-03"
    stmt = block.statements[0]
    assert "partitionOverwriteMode = dynamic" in stmt
    assert "INSERT OVERWRITE TABLE dws.sales PARTITION (dt)" in stmt
    assert "BETWEEN '2024-05-01' AND '2024-05-03'" in stmt
    # pre/post checks still bound to the range (source_table in demo spec)
    assert "dt BETWEEN '2024-05-01' AND '2024-05-03'" in result.prechecks[0]
    assert result.postchecks and "FULL OUTER JOIN" in result.postchecks[0]


def test_overwrite_dynamic_safety():
    with pytest.raises(ValueError, match="start.*end"):
        _spec(mode="overwrite_dynamic", dialect="spark")
    with pytest.raises(ValueError, match="spark/hive only"):
        _spec(mode="overwrite_dynamic", dialect="mysql",
              source="SELECT 1 WHERE dt BETWEEN '{start}' AND '{end}'")
    with pytest.raises(ValueError, match="contiguous day range"):
        _spec(mode="overwrite_dynamic", dialect="spark",
              dates=["2024-05-01"],
              source="SELECT 1 WHERE dt BETWEEN '{start}' AND '{end}'")
    hive = generate(_spec(
        mode="overwrite_dynamic", dialect="hive",
        source="SELECT 1 FROM s WHERE dt BETWEEN '{start}' AND '{end}'"))
    assert any("nonstrict" in w for w in hive.warnings)


def test_runner_script():
    result = generate(_spec(runner="spark-sql"))
    script = result.runner_script
    assert script.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in script
    # one heredoc block per date, executed via the runner command
    assert script.count("ST_BACKFILL_SQL") == 6  # open+close x 3 dates
    assert script.count('spark-sql -e "$SQL"') == 3
    assert "INSERT OVERWRITE TABLE dws.sales" in script
    md = render_markdown(result, lang="zh")
    assert "执行脚本" in md and "```bash" in md
    # no runner requested → no script, no section
    assert generate(parse_spec(DEMO)).runner_script == ""
    with pytest.raises(ValueError, match="runner must be"):
        _spec(runner="psql")


def test_specs_api_endpoint():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.backfill_sql.api import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    plan = ('{"tables": [{"table": "dws.sales", '
            '"missing": ["2024-05-05"], "cascade": []}]}')
    res = client.post("/api/backfillsql/specs", json={"plan": plan})
    assert res.status_code == 200
    body = res.json()
    assert body["result"][0]["table"] == "dws.sales"
    assert "```json" in body["report"]
    assert client.post("/api/backfillsql/specs",
                       json={"plan": "  "}).status_code == 400
    assert client.post("/api/backfillsql/specs",
                       json={"plan": "{broken"}).status_code == 400


def test_llm_source_fill_wiring(monkeypatch):
    """fill_specs replaces sources but rejects replies without {date};
    the API wires it behind llm=true. The LLM call is stubbed."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.backfill_sql import advisor_llm
    from seatunnel_agent.agents.data.backfill_sql.api import router

    replies = iter([
        "SELECT order_id, amount FROM ods.orders WHERE dt = '{date}'",
        "SELECT * FROM ods.users",  # placeholder lost → must be rejected
    ])
    monkeypatch.setattr(advisor_llm, "fill_source",
                        lambda spec, ddl, lang="zh": next(replies))
    specs = [{"table": "dws.sales", "source": "skeleton {date}"},
             {"table": "dim.users", "source": "skeleton {date}"}]
    warnings = advisor_llm.fill_specs(specs, ddl="CREATE TABLE ...")
    assert "order_id, amount" in specs[0]["source"]
    assert specs[1]["source"] == "skeleton {date}"  # kept
    assert warnings and "dim.users" in warnings[0]

    monkeypatch.setattr(advisor_llm, "fill_specs",
                        lambda specs, ddl, lang="zh": [])
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    plan = ('{"tables": [{"table": "dws.sales", '
            '"missing": ["2024-05-05"], "cascade": []}]}')
    res = client.post("/api/backfillsql/specs",
                      json={"plan": plan, "llm": True, "ddl": "CREATE ..."})
    assert res.status_code == 200
    assert res.json()["result"][0]["table"] == "dws.sales"


def test_report_zh_en_and_tool():
    result = generate(parse_spec(DEMO))
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "补数 SQL" in zh and "前置校验" in zh
    assert "Backfill SQL" in en and "Pre-flight checks" in en
    assert "```sql" in en
    md = backfill_sql(DEMO, lang="en")
    assert "idempotent" in md
    assert "must not be empty" in backfill_sql(" ")
    assert "bad input" in backfill_sql("{broken")
