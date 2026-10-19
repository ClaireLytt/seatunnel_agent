"""Report-section surgery + cross-page handoff parsing (Gradio-free).

Extracted verbatim from the legacy ``ui.py`` so the REST layer and the
React page share one implementation: measured sections (probe /
consistency / split-key / runtime) are appended to the analysis report,
replacing a previous run of the same section in place.
"""

from __future__ import annotations

import re

from seatunnel_agent.agents.data.data_skew.i18n import dsk


def _head_re(*heads: str) -> re.Pattern[str]:
    # Line-anchored so a report merely *quoting* the heading mid-sentence
    # is not matched there.
    return re.compile(
        r"(?m)^[ \t]{0,3}#{2,3}\s*(?:"
        + "|".join(re.escape(h.lstrip("# ")) for h in heads)
        + r")\s*$"
    )


PROBE_HEAD_RE = _head_re(dsk("zh", "prb_section"), dsk("en", "prb_section"))
CST_HEAD_RE = _head_re(dsk("zh", "cst_section"), dsk("en", "cst_section"))
SPK_HEAD_RE = _head_re(dsk("zh", "spk_section"), dsk("en", "spk_section"))
RT_HEAD_RE = _head_re(dsk("zh", "rt_section"), dsk("en", "rt_section"))
_NEXT_H2_RE = re.compile(r"(?m)^[ \t]{0,3}#{1,2}\s")

# Cookie the Data Comparison page sets alongside the SQL handoff so the
# user lands on /dataskew with side B's connection pre-filled (no password).
CONN_HANDOFF_COOKIE = "st_dataskew_conn"


def parse_conn_handoff(raw: str | None) -> dict | None:
    """Decode the ``st_dataskew_conn`` cookie into a connection dict, or
    None when absent/garbled. Pure so it is unit-testable."""
    import json
    from urllib.parse import unquote

    if not raw:
        return None
    try:
        data = json.loads(unquote(raw))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    return {
        "ds_type": str(data.get("ds_type") or "").lower(),
        "host": str(data.get("host") or ""),
        "port": str(data.get("port") or ""),
        "database": str(data.get("database") or ""),
        "username": str(data.get("username") or ""),
    }


def remove_section(report: str, head_re: re.Pattern[str]) -> str:
    """Drop one appended '## …' section (up to the next h1/h2) from the report."""
    m = head_re.search(report)
    if not m:
        return report
    nxt = _NEXT_H2_RE.search(report, m.end())
    end = nxt.start() if nxt else len(report)
    return (report[: m.start()].rstrip() + "\n\n" + report[end:].lstrip()).strip()


def append_section(report_cur: str, section: str,
                   head_re: re.Pattern[str]) -> str:
    """Replace/append one measured section on the current report."""
    report_cur = (report_cur or "").strip()
    placeholders = {dsk("zh", "dsk_report_placeholder"),
                    dsk("en", "dsk_report_placeholder")}
    if report_cur and report_cur not in placeholders:
        return remove_section(report_cur, head_re) + "\n\n" + section
    return section
