"""Deterministic core tests for the data freshness agent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from seatunnel_agent.agents.data.data_freshness import (
    parse_duration,
    parse_events,
    parse_rules,
    render_markdown,
    scan,
    scan_to_dict,
)

DEMO_DIR = Path(__file__).resolve().parents[1] / "examples" / "freshness_demo"
DEMO_TEXT = (DEMO_DIR / "updates.json").read_text(encoding="utf-8")
DEMO_RULES = (DEMO_DIR / "rules.json").read_text(encoding="utf-8")


def _verdicts(result) -> dict[str, str]:
    return {t.table: t.verdict for t in result.tables}


def test_parse_json_wrapper_and_csv():
    events = parse_events(DEMO_TEXT)
    assert len(events) == 6
    assert len(events["ods.orders"]) == 5
    csv_text = ("table,updated\n"
                "a,2024-01-02 00:00:00\n"
                "a,2024-01-01 00:00:00\n")
    events = parse_events(csv_text)
    assert [ts.day for ts in events["a"]] == [1, 2]  # sorted ascending


def test_parse_duration():
    assert parse_duration("1d") == 86400.0
    assert parse_duration("26h") == 93600.0
    assert parse_duration("1h30m") == 5400.0
    with pytest.raises(ValueError):
        parse_duration("tomorrow")


def test_demo_verdicts_cover_stalled_stale_late():
    result = scan(parse_events(DEMO_TEXT), parse_rules(DEMO_RULES))
    v = _verdicts(result)
    assert v["ods.items"] == "stalled"        # no update for > 2x 1d
    assert v["dws.sales"] == "stale"          # over the 26h max_age rule
    assert v["dwd.orders"] == "late"          # last gap > 1.25x cadence
    assert v["ods.orders"] == "ok"
    assert v["ods.users"] == "ok"
    assert v["ads.sales_report"] == "unknown"  # 2 updates, no rule
    assert result.worst() == "stalled"
    # findings sorted worst-first
    assert result.tables[0].verdict == "stalled"


def test_now_defaults_to_latest_update_and_is_overridable():
    result = scan(parse_events(DEMO_TEXT), parse_rules(DEMO_RULES))
    assert result.now.isoformat(sep=" ") == "2024-05-05 10:50:00"
    # a week later everything with a cadence has stalled
    later = scan(parse_events(DEMO_TEXT), parse_rules(DEMO_RULES),
                 now="2024-05-12 00:00:00")
    v = _verdicts(later)
    assert v["ods.orders"] == "stalled"
    assert v["dwd.orders"] == "stalled"


def test_rule_interval_beats_inference_and_patterns_match():
    rules = parse_rules(json.dumps({"ods.orders": {"interval": "2d"}}))
    result = scan(parse_events(DEMO_TEXT), rules)
    t = next(t for t in result.tables if t.table == "ods.orders")
    assert t.interval_src == "rule"
    assert t.interval_s == 2 * 86400.0


def test_render_markdown_bilingual():
    result = scan(parse_events(DEMO_TEXT), parse_rules(DEMO_RULES))
    zh = render_markdown(result, "zh")
    en = render_markdown(result, "en")
    assert "断更" in zh and "过期" in zh and "迟到" in zh and "正常的表" in zh
    assert "STALLED" in en and "STALE" in en and "LATE" in en


def test_scan_to_dict_counts_and_worst():
    data = scan_to_dict(scan(parse_events(DEMO_TEXT), parse_rules(DEMO_RULES)))
    assert data["counts"] == {"stalled": 1, "stale": 1, "late": 1,
                              "unknown": 1, "ok": 2}
    assert data["worst"] == "stalled"
    assert data["tables"][0]["verdict"] == "stalled"


def test_all_ok_report():
    events = parse_events(json.dumps(
        [{"table": "t", "updated": f"2024-05-0{d} 01:00:00"}
         for d in range(1, 6)]))
    result = scan(events)
    assert _verdicts(result) == {"t": "ok"}
    assert "正常" in render_markdown(result, "zh")


def test_bad_inputs_raise():
    with pytest.raises(ValueError):
        parse_events("")
    with pytest.raises(ValueError):
        parse_events('[{"updated": "2024-01-01"}]')     # missing table
    with pytest.raises(ValueError):
        parse_events('[{"table": "a"}]')                # missing timestamp
    with pytest.raises(ValueError):
        parse_rules('["not", "an", "object"]')
    with pytest.raises(ValueError):
        scan({})
