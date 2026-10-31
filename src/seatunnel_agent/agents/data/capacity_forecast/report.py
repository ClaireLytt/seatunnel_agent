"""Render a CapacityResult as markdown."""

from __future__ import annotations

import json

from seatunnel_agent.common.utils import md_table, normalize_lang

from .forecaster import _WINDOW, CapacityResult, CfFinding
from .i18n import tp

__all__ = ["render_markdown"]

_TOP_TRENDS = 10


def _detail(f: CfFinding, lang: str) -> str:
    d = dict(f.detail)
    if f.code == "CF002":
        d["top"] = "; ".join(
            f"`{t['metric']}` {t['daily_growth']:+g}/d "
            f"({t['share_pct']}%)" for t in d["top"])
    elif f.code == "CF003":
        d["metrics"] = ", ".join(
            f"`{m['metric']}` {m['daily_growth']:+g}/d"
            for m in d["metrics"])
    try:
        return tp(lang, f.code).format(**d)
    except (KeyError, IndexError, ValueError):
        return f"{tp(lang, f.code)} — {json.dumps(f.detail, ensure_ascii=False)}"


def render_markdown(result: CapacityResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    days = (tp(lang, "rpt_days").format(d=round(result.days_left, 1))
            if result.days_left is not None else "")
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(
                 quota=result.quota, total=result.total_latest,
                 growth=result.total_daily_growth,
                 exhaustion=result.exhaustion_date, days=days), ""]
    if result.findings:
        lines.append(f"### {tp(lang, 'rpt_findings')}")
        rows = [[f.code, tp(lang, "sev_" + f.severity), _detail(f, lang)]
                for f in result.findings]
        lines += md_table([tp(lang, "col_code"), tp(lang, "col_sev"),
                           tp(lang, "col_detail")], rows)
    else:
        lines.append(tp(lang, "rpt_no_findings"))
    lines += ["", f"### {tp(lang, 'rpt_trends')}"]
    rows = [[f"`{t.metric}`", f"{t.latest:g}", f"{t.daily_growth:+g}",
             str(t.points)] for t in result.trends[:_TOP_TRENDS]]
    lines += md_table([tp(lang, "col_metric"), tp(lang, "col_latest"),
                       tp(lang, "col_growth"), tp(lang, "col_points")],
                      rows)
    lines += ["", tp(lang, "rpt_disclaimer").format(window=_WINDOW)]
    return "\n".join(lines)
