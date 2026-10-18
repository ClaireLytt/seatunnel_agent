import sys
sys.path.insert(0, "src")
from seatunnel_agent.agents.devops.ui_testing.coverage import compute_coverage
from seatunnel_agent.agents.devops.ui_testing.loader import load_cases

cases = load_cases()
cov = compute_coverage(cases)
print("current:", cov.counts(), "rows:", len(cov.rows))
dc_files = {"compare.yaml", "connect.yaml", "misc.yaml", "profile_checksum.yaml",
            "aa_guards.yaml", "batch_sql_report.yaml", "sidebar.yaml"}
kept = [c for c in cases if getattr(c, "source", getattr(c, "file", None)) ]
print("case attrs:", vars(cases[0]).keys() if hasattr(cases[0], "__dict__") else cases[0])
