"""The governance demo directory feeds every governance agent.

Pins examples/governance_demo so the planted issues do not rot: each
agent must keep finding its own kind of trouble there.
"""

from __future__ import annotations

from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "examples" / "governance_demo"


def test_demo_feeds_every_governance_agent():
    from seatunnel_agent.agents.data.contract_check import (
        check_dir as contract_dir,
    )
    from seatunnel_agent.agents.data.ddl_guard import scan_dir as guard_dir
    from seatunnel_agent.agents.data.grant_scan import scan_dir as grants_dir
    from seatunnel_agent.agents.data.lineage_hygiene import analyze_dir
    from seatunnel_agent.agents.data.metadata_quality import check_dir
    from seatunnel_agent.agents.data.pii_scan import scan_dir as pii_dir

    assert pii_dir(DEMO).findings, "PII demo columns vanished"

    h = analyze_dir(DEMO).counts()
    assert h["orphan_outputs"] >= 1 and h["dangling_defs"] >= 1

    m = check_dir(DEMO)
    kinds = {f.kind for f in m.findings}
    assert {"money_float", "date_string", "layer_naming",
            "unpartitioned_fact", "missing_owner"} <= kinds

    contract_text = (DEMO / "contract.yaml").read_text(encoding="utf-8")
    c = contract_dir(DEMO, contract=contract_text)
    ckinds = {f.kind for f in c.findings}
    assert {"type_mismatch", "missing_column", "partition_mismatch"} <= ckinds

    g = grants_dir(DEMO)
    gkinds = {f.kind for f in g.findings}
    assert {"public_grant", "sensitive_grant", "broad_privilege",
            "wide_scope"} <= gkinds

    d = guard_dir(DEMO)
    dkinds = {f.kind for f in d.findings}
    assert {"drop_table", "drop_column", "truncate_table",
            "type_narrowing", "rename_table"} <= dkinds
    assert d.undo_sql


def test_demo_contract_init_round_trips():
    from seatunnel_agent.agents.data.contract_check import check_dir
    from seatunnel_agent.agents.data.contract_check.bootstrap import (
        generate_from_dir,
    )

    draft = generate_from_dir(DEMO)
    # the generated contract reflects current state, so it gates clean
    assert check_dir(DEMO, contract=draft).counts()["total"] == 0
