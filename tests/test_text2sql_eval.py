"""Tests for the end-to-end eval harness (dataset, result comparison,
run_eval with a fake agent runner on sqlite)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from seatunnel_agent.text2sql.evaluate import (
    EvalCase,
    load_dataset,
    render_eval_report,
    results_match,
    run_eval,
)
from seatunnel_agent.text2sql.executor import DatabaseConfig
from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl

_FIXTURE = Path(__file__).parent / "fixtures" / "t2s_eval_demo.jsonl"


def test_load_dataset_fixture() -> None:
    cases = load_dataset(_FIXTURE)
    assert len(cases) == 20
    assert all(c.question and c.golden_sql.upper().startswith("SELECT")
               for c in cases)


def test_load_dataset_errors(tmp_path) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"question": "x"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="golden_sql"):
        load_dataset(bad)


def test_results_match_semantics() -> None:
    ok, _ = results_match([(1, "a")], [("1.0", "a")])   # numeric strings
    assert ok
    ok, _ = results_match([(1,), (2,)], [(2,), (1,)])   # order-insensitive
    assert ok
    ok, _ = results_match([(0.1 + 0.2,)], [(0.3,)])     # float tolerance
    assert ok
    ok, _ = results_match([(1, "a")], [(1, "a", "extra")])  # extra col ok
    assert ok
    ok, diff = results_match([(1,)], [(2,)])
    assert not ok and "missing" in diff


def test_run_eval_with_fake_runner(tmp_path) -> None:
    db = tmp_path / "e.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE s(city TEXT, amount REAL)")
    conn.executemany("INSERT INTO s VALUES (?,?)",
                     [("bj", 10.0), ("sh", 20.0), ("bj", 5.0)])
    conn.commit()
    conn.close()
    store = SchemaStore(parse_ddl("CREATE TABLE s(city string, amount double) COMMENT 'x';"))
    db_config = DatabaseConfig(ds_type="sqlite", host="", port=0, database=str(db))

    answers = {
        "各城市销售额": ("SELECT city, SUM(amount) AS a FROM s GROUP BY city",
                        [("sh", 20.0), ("bj", 15.0)]),      # correct (reordered)
        "总销售额": ("SELECT SUM(amount) FROM s", [(999.0,)]),  # wrong number
    }

    def fake_runner(question: str):
        if question == "会崩的问题":
            raise RuntimeError("LLM exploded")
        return answers[question]

    cases = [
        EvalCase("各城市销售额", "SELECT city, SUM(amount) FROM s GROUP BY city"),
        EvalCase("总销售额", "SELECT SUM(amount) FROM s"),
        EvalCase("会崩的问题", "SELECT COUNT(*) FROM s"),
        EvalCase("坏golden", "SELECT * FROM not_whitelisted"),
    ]
    report = run_eval(cases, fake_runner, db_config, store=store)
    by_q = {c.question: c for c in report.cases}
    assert by_q["各城市销售额"].status == "pass"
    assert by_q["总销售额"].status == "fail"
    assert by_q["会崩的问题"].status == "error"
    assert "agent failed" in by_q["会崩的问题"].detail
    assert by_q["坏golden"].status == "error"
    assert "rejected" in by_q["坏golden"].detail
    assert report.accuracy == 0.25

    text = render_eval_report(report, model_name="fake-model")
    assert "25.0%" in text and "fake-model" in text
    assert "总销售额" in text


def test_eval_dataset_golden_sql_runs_on_seeded_db(tmp_path) -> None:
    """Every golden SQL in the shipped dataset must actually run against the
    seeded demo db — the dataset itself is gated."""
    from seatunnel_agent.text2sql.executor import create_executor
    from seatunnel_agent.ui_testing.seed_sqlite import seed_sqlite

    db = tmp_path / "demo.db"
    seed_sqlite(str(db))
    executor = create_executor(
        DatabaseConfig(ds_type="sqlite", host="", port=0, database=str(db)))
    for case in load_dataset(_FIXTURE):
        result = executor.run(case.golden_sql, max_rows=100)
        assert result.columns, case.question
