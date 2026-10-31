"""Deep seam for the check-shaped CLI surface.

The governance commands (pii / hygiene / metaquality) grew the same
implicit interface: take --dir/--sql/--file, analyze, emit markdown or
json, optionally save, log a history record and gate the CI with exit 1.
Three adapters make the seam real — :class:`CheckSpec` names it once and
each command shrinks to a spec plus its own quirks (pii's --mask branch,
hygiene's exemption YAML).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from ..common.cli_common import console

SEVERITY_RANK = {"info": 1, "low": 1, "medium": 2, "high": 3}

_REPORT_OPTIONS = [
    click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
                 show_default=True, help="Report language"),
    click.option("--format", "-F", "fmt",
                 type=click.Choice(["markdown", "json"]),
                 default="markdown", help="Report format"),
    click.option("--output", "-o", type=click.Path(), default=None,
                 help="Save report to file"),
]


def report_options(fn):
    """The --lang/--format/--output trio every report command takes."""
    for deco in reversed(_REPORT_OPTIONS):
        fn = deco(fn)
    return fn


def require_with(flag_set: Any, flag: str, dep: str) -> None:
    """Fail with the standard message when *flag* is used without *dep*."""
    if flag_set:
        raise click.UsageError(f"{flag} 需配合 {dep}")


def read_input(path: str | None, text: str | None, what: str) -> str:
    """Resolve the --file/--text pair every analyze command takes."""
    if path:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    if text:
        return text
    raise click.UsageError(f"提供 --file 或 --text（{what}）")


@dataclass(frozen=True)
class CheckSpec:
    """Everything a command must declare to run a standard check."""

    # analyze entry points; ``extras`` flow through as keyword arguments
    analyze_dir: Callable[..., Any]    # (directory, dialect=..., **extras)
    analyze_file: Callable[..., Any]   # ([Path], dialect=..., root=..., **extras)
    analyze_sql: Callable[..., Any]    # (sql, dialect=..., **extras)
    render: Callable[[Any, str], str]             # (report, lang) -> markdown
    to_dict: Callable[[Any, str], dict[str, Any]]  # (report, lang) -> payload
    error_label: str                               # e.g. "扫描失败"
    # CI gate: (report, fail_on) -> failure message, or None to pass
    gate: Callable[[Any, str], str | None] | None = None
    log_run: Callable[[Any], None] | None = None   # cli-source history hook


def analyze_input(spec: CheckSpec, directory: str | None, sql: str | None,
                  sql_file: str | None, dialect: str, **extras: Any) -> Any:
    """Resolve the --dir/--sql/--file trio into one report."""
    if not directory and not sql and not sql_file:
        raise click.UsageError("Provide --dir / --sql / --file")
    try:
        if directory:
            return spec.analyze_dir(directory, dialect=dialect, **extras)
        if sql_file:
            return spec.analyze_file([Path(sql_file)], dialect=dialect,
                                     root=sql_file, **extras)
        return spec.analyze_sql(sql or "", dialect=dialect, **extras)
    except (OSError, UnicodeDecodeError) as exc:
        console.print(f"[red]{spec.error_label}:[/red] {exc}")
        sys.exit(1)


def save_output(text_out: str, output: str | None) -> None:
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")


def emit_report(spec: CheckSpec, report: Any, lang: str, fmt: str,
                output: str | None) -> None:
    if fmt == "json":
        text_out = json.dumps(spec.to_dict(report, lang),
                              ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = spec.render(report, lang)
        console.print(text_out, markup=False)
    save_output(text_out, output)


def emit_payload(payload: dict[str, Any], markdown: str, fmt: str,
                 output: str | None) -> None:
    """Spec-less twin of :func:`emit_report` for commands that already
    hold the payload dict and rendered markdown."""
    if fmt == "json":
        text_out = json.dumps(payload, ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = markdown
        console.print(text_out, markup=False)
    save_output(text_out, output)


def append_jsonl(path_str: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Append *entry* with a UTC ts to a jsonl file; return the row."""
    from datetime import datetime, timezone

    path = Path(path_str)
    entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             **entry}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def track_history(history_path: str, entry: dict[str, Any],
                  worse_key: str) -> None:
    """Append *entry* (plus a ts) to the jsonl; print the drift vs the
    previous record — yellow when *worse_key* grew, dim otherwise."""
    path = Path(history_path)
    previous = None
    if path.is_file():
        lines = [ln for ln in
                 path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if lines:
            previous = json.loads(lines[-1])
    entry = append_jsonl(history_path, entry)
    if previous is None:
        console.print(f"[dim]history: 首次记录 → {path}[/dim]")
        return
    deltas = [f"{k} {previous.get(k, 0):g} → {v:g}"
              for k, v in entry.items()
              if k != "ts" and v != previous.get(k, 0)]
    if deltas:
        worse = entry[worse_key] > previous.get(worse_key, 0)
        tone = "yellow" if worse else "dim"
        console.print(f"[{tone}]history({previous.get('ts', '?')} → 本次): "
                      + " · ".join(deltas) + f"[/{tone}]")
    else:
        console.print("[dim]history: 与上次记录持平[/dim]")


def fail_check(msg: str, fmt: str) -> None:
    """Report a failed gate and exit 1 (stderr keeps json stdout clean)."""
    if fmt == "json":
        print(msg, file=sys.stderr)
    else:
        console.print(f"\n[red]{msg}[/red]")
    sys.exit(1)


def severity_gate(findings: Iterable[Any], fail_on: str, msg: str) -> str | None:
    """Standard rank gate: fail when any finding reaches ``fail_on``."""
    worst = max((SEVERITY_RANK[f.severity] for f in findings), default=0)
    return msg if worst >= SEVERITY_RANK[fail_on] else None


def run_check(spec: CheckSpec, *, directory: str | None, sql: str | None,
              sql_file: str | None, dialect: str, lang: str, fmt: str,
              output: str | None, fail_on: str | None,
              **extras: Any) -> Any:
    """The whole standard path: analyze, emit, log, gate."""
    report = analyze_input(spec, directory, sql, sql_file, dialect, **extras)
    emit_report(spec, report, lang, fmt, output)
    if spec.log_run is not None:
        spec.log_run(report)
    if fail_on and spec.gate is not None:
        msg = spec.gate(report, fail_on)
        if msg:
            fail_check(msg, fmt)
    return report
