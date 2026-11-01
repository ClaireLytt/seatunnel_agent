"""Render a CostBill as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .allocator import CostBill
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(bill: CostBill, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(owners=len(bill.owners),
                                          total=round(bill.total, 2),
                                          sp=bill.storage_price,
                                          cp=bill.compute_price,
                                          unalloc=bill.unallocated_share),
             "", f"### {tp(lang, 'rpt_owners')}"]
    rows = []
    for o in bill.owners:
        name = (tp(lang, "unallocated")
                if o.owner == "(unallocated)" else f"`{o.owner}`")
        share = o.total / bill.total if bill.total else 0.0
        top = ", ".join(f"`{n}` {c:g}" for n, c in o.top_items[:2])
        rows.append([name, str(o.items), f"{o.storage_cost:g}",
                     f"{o.compute_cost:g}", f"{o.total:g}",
                     f"{share:.1%}", top or "-"])
    lines += md_table([tp(lang, "col_owner"), tp(lang, "col_items"),
                       tp(lang, "col_storage"), tp(lang, "col_compute"),
                       tp(lang, "col_total"), tp(lang, "col_share"),
                       tp(lang, "col_top")], rows)
    if not bill.findings:
        lines += ["", tp(lang, "rpt_clean")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        rows = [[SEVERITY_MARK[f.severity], f.code,
                 tp(lang, "unallocated")
                 if f.owner == "(unallocated)" else f"`{f.owner}`",
                 tp(lang, f.code).format(value=f.value)]
                for f in bill.findings]
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_code"),
                           tp(lang, "col_owner"), tp(lang, "col_issue")],
                          rows)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
