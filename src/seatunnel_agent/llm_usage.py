"""Cross-agent LLM token usage log.

``LLMClient.chat`` appends one JSONL line per call to
``logs/llm_usage.jsonl`` ({ts, provider, model, input, output}), so every
agent is covered by a single hook.  The settings page and
``seatunnel-agent settings --usage`` render :func:`summarize`.

Env knobs: ``LLM_USAGE_LOG=0`` disables recording, ``LLM_USAGE_PATH``
relocates the file (tests point it at a tmp dir).
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .jsonl_log import JsonlLog


def usage_path() -> Path:
    return Path(os.getenv("LLM_USAGE_PATH") or "logs/llm_usage.jsonl")


_log = JsonlLog(usage_path, env_switch="LLM_USAGE_LOG")


def record(provider: str, model: str, usage: dict[str, Any] | None,
           agent: str | None = None) -> None:
    """Append one call's usage; must never raise into the LLM call path.

    *agent* optionally attributes the call to a feature (``text2sql``,
    ``sql_review``, …) for per-agent cost roll-ups; omitted calls land in
    the "unattributed" bucket."""
    try:
        usage = usage or {}
        # LLMClient populates input_tokens/output_tokens; accept the short
        # forms too (this mismatch once logged every real call as 0 tokens)
        inp = usage.get("input_tokens", usage.get("input", 0)) or 0
        out = usage.get("output_tokens", usage.get("output", 0)) or 0
        rec: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "provider": provider,
            "model": model,
            "input": int(inp),
            "output": int(out),
        }
        if agent:
            rec["agent"] = agent
    except Exception:  # noqa: BLE001 — usage logging is best-effort
        return
    _log.append(rec)


def summarize(days: int = 30) -> dict[str, Any]:
    """Totals for the last N days: overall, per model, per day (UTC)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    total = {"calls": 0, "input": 0, "output": 0}
    by_model: dict[str, dict[str, int]] = defaultdict(
        lambda: {"calls": 0, "input": 0, "output": 0})
    by_day: dict[str, int] = defaultdict(int)
    try:
        text = usage_path().read_text(encoding="utf-8")
    except OSError:
        return {"days": days, "total": total, "by_model": {}, "by_day": {}}
    for line in text.splitlines():
        try:
            rec = json.loads(line)
            ts = datetime.strptime(rec["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
        except (ValueError, KeyError, TypeError):
            continue
        if ts < cutoff:
            continue
        inp = int(rec.get("input", 0) or 0)
        out = int(rec.get("output", 0) or 0)
        total["calls"] += 1
        total["input"] += inp
        total["output"] += out
        m = by_model[str(rec.get("model", "?"))]
        m["calls"] += 1
        m["input"] += inp
        m["output"] += out
        by_day[ts.strftime("%Y-%m-%d")] += inp + out
    return {"days": days, "total": total,
            "by_model": dict(by_model), "by_day": dict(by_day)}


def format_markdown(lang: str = "en", days: int = 30) -> str:
    """Bilingual markdown block for the settings page."""
    s = summarize(days)
    zh = lang == "zh"
    if not s["total"]["calls"]:
        return "暂无 LLM 调用记录" if zh else "No LLM calls recorded yet"
    t = s["total"]
    head = (f"近 {days} 天:{t['calls']} 次调用 · 输入 {t['input']:,} · "
            f"输出 {t['output']:,} tokens") if zh else (
        f"Last {days} days: {t['calls']} calls · {t['input']:,} in · "
        f"{t['output']:,} out tokens")
    rows = ["| " + ("模型 | 调用 | 输入 | 输出" if zh
                    else "Model | Calls | Input | Output") + " |",
            "|---|---|---|---|"]
    for model, m in sorted(s["by_model"].items(),
                           key=lambda kv: -(kv[1]["input"] + kv[1]["output"])):
        rows.append(f"| `{model}` | {m['calls']} | {m['input']:,} "
                    f"| {m['output']:,} |")
    return head + "\n\n" + "\n".join(rows)
