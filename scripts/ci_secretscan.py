"""CI gate: run the secret scanner over src/ and scripts/ without the CLI.

The CLI import chain pulls optional deps (sqlglot, ...); this script imports
only the scanner package (stdlib + pyyaml), so the job needs just
`pip install -e . pyyaml`. Exits 1 when any high-severity finding survives
the repo-root .secretscan.yaml exemptions — same contract as
`seatunnel-agent secretscan src scripts --fail-on high`.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.path.insert(0, str(REPO / "src"))
    from seatunnel_agent.agents.devops.secret_scan.scanner import (
        load_config,
        scan_paths,
    )

    result = scan_paths([REPO / "src", REPO / "scripts"],
                        config=load_config(REPO), root=REPO)
    sev = result.severities
    print(f"files scanned {result.files_scanned} · skipped "
          f"{result.files_skipped} · findings {len(result.findings)} "
          f"(high {sev.get('high', 0)} / medium {sev.get('medium', 0)} / "
          f"low {sev.get('low', 0)})")
    for f in result.findings:
        print(f"  [{f.severity}] {f.rule_id} {f.file}:{f.line} {f.masked}")
    if sev.get("high", 0):
        print("FAIL: high-severity findings present")
        return 1
    print("PASS: no high-severity findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
