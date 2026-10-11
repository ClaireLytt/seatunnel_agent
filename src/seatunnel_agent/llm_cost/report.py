# -*- coding: utf-8 -*-
"""Bilingual markdown report for the LLM cost summary."""

from __future__ import annotations

from typing import Any

from .i18n import normalize_lang, tp


def _usd(v: float) -> str:
    return f"${v:,.4f}" if v < 1 else f"${v:,.2f}"


def render_markdown(summary: dict[str, Any], lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    t = summary["total"]
    lines: list[str] = [f"## {tp(lang, 'rpt_title')}", ""]
    lines.append(tp(lang, "rpt_total").format(
        days=summary["days"], calls=t["calls"], cost=_usd(t["cost_usd"]),
        inp=t["input"], out=t["output"]))
    if not t["calls"]:
        lines.append("")
        lines.append(tp(lang, "rpt_empty"))
        return "\n".join(lines)

    lines.append("")
    lines.append("| " + tp(lang, "rpt_model_header") + " |")
    lines.append("|---|---|---|---|---|")
    for model, b in sorted(summary["by_model"].items(),
                           key=lambda kv: -kv[1]["cost_usd"]):
        cost = (_usd(b["cost_usd"]) if not b["unpriced_calls"]
                else tp(lang, "rpt_unpriced_cell"))
        lines.append(f"| `{model}` | {b['calls']} | {b['input']:,} "
                     f"| {b['output']:,} | {cost} |")

    agents = {a: b for a, b in summary["by_agent"].items()
              if a != "unattributed"}
    if agents:
        lines.append("")
        lines.append("| " + tp(lang, "rpt_agent_header") + " |")
        lines.append("|---|---|---|")
        for agent, b in sorted(agents.items(),
                               key=lambda kv: -kv[1]["cost_usd"]):
            lines.append(f"| `{agent}` | {b['calls']} | {_usd(b['cost_usd'])} |")

    if summary["anomalies"]:
        lines.append("")
        lines.append(f"### {tp(lang, 'rpt_anomaly_title')}")
        for a in summary["anomalies"]:
            lines.append(tp(lang, "rpt_anomaly_item").format(
                day=a["day"], cost=_usd(a["cost_usd"]),
                baseline=_usd(a["baseline_usd"])))

    if summary["unpriced_models"]:
        lines.append("")
        lines.append(tp(lang, "rpt_unpriced_warn").format(
            models=", ".join(f"`{m}`" for m in summary["unpriced_models"])))

    lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
