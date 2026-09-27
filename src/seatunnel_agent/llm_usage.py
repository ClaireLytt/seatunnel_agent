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
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_MAX_LOG_BYTES = 10 * 1024 * 1024
_lock = threading.Lock()


def usage_path() -> Path:
    return Path(os.getenv("LLM_USAGE_PATH") or "logs/llm_usage.jsonl")


def record(provider: str, model: str, usage: dict[str, Any] | None) -> None:
    """Append one call's usage; must never raise into the LLM call path."""
    if os.getenv("LLM_USAGE_LOG", "1") == "0":
        return
    try:
        usage = usage or {}
        line = json.dumps({
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "provider": provider,
            "model": model,
            "input": int(usage.get("input", 0) or 0),
            "output": int(usage.get("output", 0) or 0),
        }, ensure_ascii=False)
        path = usage_path()
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.is_file() and path.stat().st_size > _MAX_LOG_BYTES:
                lines = path.read_text(encoding="utf-8").splitlines()
                path.write_text("\n".join(lines[len(lines) // 2:]) + "\n",
                                encoding="utf-8")
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception:  # noqa: BLE001 — usage logging is best-effort
        pass


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
