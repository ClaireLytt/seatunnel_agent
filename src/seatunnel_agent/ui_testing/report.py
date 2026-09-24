"""Run reports: result.json (machine-readable) + report.html (single file).

Secrets are masked everywhere: any value of a ``*_PASSWORD``/``*API_KEY``/
``*SECRET*``/``*TOKEN*`` variable found in .env or the environment is
replaced by ``***`` before anything is written.
"""

from __future__ import annotations

import base64
import dataclasses
import html
import json
import os
import re
from pathlib import Path

from .models import CaseResult, RunResult

_SECRET_KEY_RE = re.compile(r"(PASSWORD|API_KEY|SECRET|TOKEN)", re.IGNORECASE)


def _secret_values() -> list[str]:
    vals: set[str] = set()
    for k, v in os.environ.items():
        if _SECRET_KEY_RE.search(k) and v and len(v) >= 6:
            vals.add(v)
    env_file = Path(".env")
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8",
                                       errors="replace").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            k, _, v = line.partition("=")
            v = v.strip().strip("'\"")
            if _SECRET_KEY_RE.search(k) and v and len(v) >= 6:
                vals.add(v)
    return sorted(vals, key=len, reverse=True)


def mask(text: str) -> str:
    for v in _secret_values():
        text = text.replace(v, "***")
    return text


def write_json(rr: RunResult, run_dir: Path) -> Path:
    path = run_dir / "result.json"
    data = json.loads(mask(json.dumps(dataclasses.asdict(rr),
                                      ensure_ascii=False)))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


# ── HTML report ──

_VERDICT_COLOR = {
    "PASS": "#16a34a", "FAIL": "#dc2626", "ERROR": "#ea580c",
    "SKIP": "#9ca3af", "MANUAL": "#6366f1",
}

_CSS = """
:root{--bg:#f8fafc;--card:#fff;--line:#e2e8f0;--txt:#0f172a;--mut:#64748b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);
font:14px/1.6 -apple-system,'Segoe UI','Microsoft YaHei',sans-serif;padding:24px}
.wrap{max-width:1080px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}
.meta{color:var(--mut);font-size:13px;margin-bottom:16px}
.stats{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:10px 18px;text-align:center;cursor:pointer;min-width:86px}
.stat.active{outline:2px solid #3b82f6}
.stat b{display:block;font-size:22px}.stat span{font-size:12px;color:var(--mut)}
.case{background:var(--card);border:1px solid var(--line);border-radius:10px;
margin-bottom:10px;overflow:hidden}
.case>summary{padding:10px 16px;cursor:pointer;display:flex;gap:12px;
align-items:center;list-style:none}
.case>summary::-webkit-details-marker{display:none}
.badge{font-weight:700;font-size:12px;padding:2px 10px;border-radius:99px;
color:#fff;min-width:52px;text-align:center}
.cid{font-weight:700;min-width:38px}.ctitle{flex:1}
.cmeta{color:var(--mut);font-size:12px;white-space:nowrap}
.body{padding:4px 16px 14px;border-top:1px solid var(--line)}
.reason{color:#dc2626;margin:8px 0;font-weight:600}
table{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0}
th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);
vertical-align:top}th{color:var(--mut);font-weight:600;font-size:12px}
td.ok{color:#16a34a}td.bad{color:#dc2626}
.shot{max-width:100%;border:1px solid var(--line);border-radius:8px;margin:8px 0}
.applog{background:#0f172a;color:#e2e8f0;border-radius:8px;padding:12px;
font:12px/1.5 Consolas,monospace;white-space:pre-wrap;max-height:320px;
overflow:auto}
"""

_FILTER_JS = """
document.querySelectorAll('.stat').forEach(s=>s.addEventListener('click',()=>{
  const v=s.dataset.v;
  document.querySelectorAll('.stat').forEach(x=>x.classList.toggle('active',x===s&&v!=='ALL'));
  document.querySelectorAll('.case').forEach(c=>{
    c.style.display=(v==='ALL'||c.dataset.v===v)?'':'none';});
}));
"""


def _esc(s: str) -> str:
    return html.escape(mask(str(s)))


def _step_rows(logs, run_dir: Path) -> str:
    rows = []
    for lg in logs:
        cls = "ok" if lg.ok else "bad"
        mark = "✓" if lg.ok else "✗"
        shot = ""
        if lg.screenshot:
            p = run_dir / lg.screenshot
            if p.is_file():
                b64 = base64.b64encode(p.read_bytes()).decode()
                shot = (f'<img class="shot" alt="screenshot" '
                        f'src="data:image/png;base64,{b64}">')
        rows.append(
            f'<tr><td class="{cls}">{mark}</td>'
            f'<td>{_esc(lg.desc)}</td>'
            f'<td>{_esc(lg.detail)}{shot}</td>'
            f'<td>{lg.elapsed_ms}ms</td></tr>')
    return "".join(rows)


def _case_html(c: CaseResult, run_dir: Path) -> str:
    color = _VERDICT_COLOR.get(c.verdict, "#64748b")
    body = ""
    if c.reason:
        body += f'<div class="reason">{_esc(c.reason)}</div>'
    if c.steps:
        body += ('<table><tr><th></th><th>步骤</th><th>明细</th><th>耗时</th></tr>'
                 + _step_rows(c.steps, run_dir) + "</table>")
    if c.asserts:
        body += ('<table><tr><th></th><th>断言</th><th>期望 vs 实际</th><th>耗时</th></tr>'
                 + _step_rows(c.asserts, run_dir) + "</table>")
    tok = f" · {c.tokens} tok" if c.tokens else ""
    return (
        f'<details class="case" data-v="{c.verdict}"'
        + (" open" if c.verdict in ("FAIL", "ERROR") else "") + ">"
        f'<summary><span class="badge" style="background:{color}">'
        f'{c.verdict}</span><span class="cid">{_esc(c.case_id)}</span>'
        f'<span class="ctitle">{_esc(c.title)}</span>'
        f'<span class="cmeta">{c.elapsed_ms / 1000:.1f}s{tok}</span></summary>'
        f'<div class="body">{body or "<p>无明细</p>"}</div></details>')


def write_html(rr: RunResult, run_dir: Path) -> Path:
    counts = rr.counts()
    stats = ['<div class="stat active" data-v="ALL"><b>'
             f'{len(rr.cases)}</b><span>全部</span></div>']
    for k in ("PASS", "FAIL", "ERROR", "SKIP", "MANUAL"):
        stats.append(
            f'<div class="stat" data-v="{k}">'
            f'<b style="color:{_VERDICT_COLOR[k]}">{counts[k]}</b>'
            f'<span>{k}</span></div>')

    cases_html = "".join(_case_html(c, run_dir) for c in rr.cases)
    applog = ""
    if rr.app_log_tail and (counts["FAIL"] or counts["ERROR"]):
        applog = ("<h2 style='font-size:16px'>被测应用日志(尾部)</h2>"
                  f'<div class="applog">{_esc(rr.app_log_tail)}</div>')

    doc = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>UI 测试报告 · {rr.started_at}</title><style>{_CSS}</style></head>
<body><div class="wrap">
<h1>UI 测试报告</h1>
<div class="meta">套件: {_esc(rr.suite)} · 开始: {rr.started_at} ·
耗时: {rr.elapsed_ms / 1000:.0f}s · LLM: {rr.tokens} tokens</div>
<div class="stats">{"".join(stats)}</div>
{cases_html}
{applog}
</div><script>{_FILTER_JS}</script></body></html>"""

    path = run_dir / "report.html"
    path.write_text(doc, encoding="utf-8")
    return path


def print_summary(rr: RunResult) -> None:
    counts = rr.counts()
    print()
    print("─" * 62)
    for c in rr.cases:
        mark = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥",
                "SKIP": "⏭️", "MANUAL": "📝"}.get(c.verdict, "?")
        line = f"{mark} {c.verdict:<6} {c.case_id:<5} {c.title}"
        if c.reason and c.verdict in ("FAIL", "ERROR"):
            line += f"  — {mask(c.reason)[:70]}"
        print(line)
    print("─" * 62)
    print(f"PASS {counts['PASS']} · FAIL {counts['FAIL']} · "
          f"ERROR {counts['ERROR']} · SKIP {counts['SKIP']} · "
          f"MANUAL {counts['MANUAL']} · 耗时 {rr.elapsed_ms / 1000:.0f}s"
          + (f" · {rr.tokens} tokens" if rr.tokens else ""))
