"""Render a LagResult as markdown."""

from __future__ import annotations

import json

from seatunnel_agent.common.utils import md_table, normalize_lang

from .analyzer import KafkaFinding, LagResult
from .i18n import tp

__all__ = ["render_markdown"]

_TOP_PARTS = 10


def _detail(f: KafkaFinding, lang: str) -> str:
    d = dict(f.detail)
    if f.code == "KL003":
        d["top"] = "; ".join(
            f"{b['topic']}[{b['partition']}] lag {b['lag']} "
            f"({b['consume_rate']:g}/{b['produce_rate']:g})"
            for b in d["top"])
    try:
        return tp(lang, f.code).format(**d)
    except (KeyError, IndexError, ValueError):
        return f"{tp(lang, f.code)} — {json.dumps(f.detail, ensure_ascii=False)}"


def render_markdown(result: LagResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(group=result.group or "?",
                                          parts=len(result.partitions),
                                          total=result.total_lag), ""]
    if result.findings:
        lines.append(f"### {tp(lang, 'rpt_findings')}")
        rows = [[f.code, tp(lang, "sev_" + f.severity), _detail(f, lang),
                 tp(lang, "rx_" + f.code)] for f in result.findings]
        lines += md_table([tp(lang, "col_code"), tp(lang, "col_sev"),
                           tp(lang, "col_detail"), tp(lang, "col_rx")],
                          rows)
    else:
        lines.append(tp(lang, "rpt_clean"))
    shown = [p for p in result.partitions if p.lag > 0][:_TOP_PARTS]
    if shown:
        lines += ["", f"### {tp(lang, 'rpt_partitions')}"]
        rows = []
        for p in shown:
            produce = ("?" if p.produce_rate is None
                       else f"{p.produce_rate:g}")
            rates = ("-" if p.consume_rate is None
                     else f"{p.consume_rate:g}/{produce}")
            rows.append([f"`{p.topic}[{p.partition}]`", str(p.lag),
                         f"{p.committed_offset} → {p.log_end_offset}",
                         rates])
        lines += md_table([tp(lang, "col_topic"), tp(lang, "col_lag"),
                           tp(lang, "col_offsets"), tp(lang, "col_rates")],
                          rows)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
