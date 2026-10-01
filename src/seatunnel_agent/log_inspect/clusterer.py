# -*- coding: utf-8 -*-
"""Deterministic log-event extraction and exception clustering.

Event model: an ERROR/WARN/FATAL log line (or a bare exception trace)
starts an event; stack frames, ``Caused by:`` lines and indented
continuations attach to it.  The cluster signature prefers the *root
cause* — the last ``Caused by:`` exception — over the outer wrapper, and
masks volatile parts of the message (numbers, paths, addresses, ids) so
the same failure from different jobs lands in one cluster.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

DEFAULT_PATTERNS = ("*.log", "*.log.*", "*.out", "*.err")
MAX_FILE_BYTES = 50 * 1024 * 1024    # per-file cap: a runaway log is truncated
MAX_SAMPLE_LINES = 25
MAX_EVENTS_PER_FILE = 20_000

import re

_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?")
_LEVEL_RE = re.compile(r"\b(FATAL|ERROR|WARN(?:ING)?)\b")
# an INFO/DEBUG/TRACE token BEFORE the ERROR/WARN hit means the line's level
# is informational and merely mentions the word (e.g. "state changed to ERROR")
_CALM_RE = re.compile(r"\b(INFO|DEBUG|TRACE)\b")
# java.lang.FooException[: message] — standalone trace head or Caused by
_EXC_RE = re.compile(
    r"(?:Caused by:\s*)?([\w$.]+(?:Exception|Error|Throwable))(?::\s*(.*))?$")
_CAUSED_RE = re.compile(r"^\s*Caused by:\s*([\w$.]+)(?::\s*(.*))?$")
# capture the method path only (no (File.java:123) suffix): clusters must
# not split when the same failure moves a few lines inside one file
_FRAME_RE = re.compile(r"^\s+at\s+([\w.$/<>]+)")
_MORE_RE = re.compile(r"^\s+\.\.\.\s+\d+\s+(more|common frames omitted)")
# `ERROR [thread] com.foo.Logger - message` → strip thread + logger prefix
_AFTER_LEVEL_RE = re.compile(r"^\s*(?:\[[^\]]*\]\s*)?(?:[\w.$]+\s*[-:]\s+)?")

# message normalization: volatile tokens → placeholders
_NORMALIZERS: tuple[tuple[re.Pattern, str], ...] = (
    (_TS_RE, "<TS>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}"
                r"-[0-9a-f]{12}\b", re.I), "<ID>"),
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "<HEX>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<ADDR>"),
    (re.compile(r"(?:[A-Za-z]:)?(?:[\\/][\w.$~-]+){2,}"), "<PATH>"),
    (re.compile(r"\b[0-9a-f]{16,}\b", re.I), "<HEX>"),
    (re.compile(r"\b\d+\b"), "<N>"),
    (re.compile(r"'[^']{24,}'"), "'<S>'"),
    (re.compile(r'"[^"]{24,}"'), '"<S>"'),
)


def normalize_message(message: str) -> str:
    out = message.strip()
    for pattern, repl in _NORMALIZERS:
        out = pattern.sub(repl, out)
    return re.sub(r"\s+", " ", out)[:300]


@dataclass
class LogEvent:
    file: str
    line_no: int
    level: str                     # error | warn
    timestamp: str = ""
    exception: str = ""            # root-cause exception class
    message: str = ""              # root-cause (or line) message
    top_frame: str = ""            # first frame under the root cause
    raw: str = ""                  # trimmed full event text

    @property
    def signature(self) -> str:
        return f"{self.exception}|{normalize_message(self.message)}|{self.top_frame}"


@dataclass
class LogCluster:
    signature: str
    level: str
    exception: str
    template: str
    top_frame: str
    count: int = 0
    files: dict[str, int] = field(default_factory=dict)
    first_ts: str = ""
    last_ts: str = ""
    sample: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "exception": self.exception,
            "template": self.template,
            "top_frame": self.top_frame,
            "count": self.count,
            "files": dict(self.files),
            "first_ts": self.first_ts,
            "last_ts": self.last_ts,
            "sample": self.sample,
        }


@dataclass
class InspectReport:
    root: str
    files_scanned: int = 0
    lines_scanned: int = 0
    events: int = 0
    clusters: list[LogCluster] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "error": sum(1 for c in self.clusters if c.level == "error"),
            "warn": sum(1 for c in self.clusters if c.level == "warn"),
            "clusters": len(self.clusters),
            "events": self.events,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "files_scanned": self.files_scanned,
            "lines_scanned": self.lines_scanned,
            "counts": self.counts(),
            "clusters": [c.to_dict() for c in self.clusters],
            "warnings": list(self.warnings),
        }


# ---------------------------------------------------------------------------
# event extraction
# ---------------------------------------------------------------------------

def _is_continuation(line: str) -> bool:
    return bool(_FRAME_RE.match(line) or _CAUSED_RE.match(line)
                or _MORE_RE.match(line)
                or (line[:1] in ("\t", " ") and line.strip()))


def _finalize(event: LogEvent, lines: list[str]) -> LogEvent:
    """Pick the root cause (last ``Caused by:``) and its top frame."""
    root_exc, root_msg, root_at = event.exception, event.message, -1
    for idx, line in enumerate(lines):
        m = _CAUSED_RE.match(line)
        if m:
            root_exc, root_msg, root_at = m.group(1), m.group(2) or "", idx
    if root_at >= 0:
        event.exception, event.message = root_exc, root_msg
        frames = lines[root_at + 1:]
    else:
        frames = lines
    for line in frames:
        fm = _FRAME_RE.match(line)
        if fm:
            event.top_frame = fm.group(1)
            break
    event.raw = "\n".join(lines[:MAX_SAMPLE_LINES]).rstrip()
    if len(lines) > MAX_SAMPLE_LINES:
        event.raw += f"\n... ({len(lines) - MAX_SAMPLE_LINES} more lines)"
    return event


def extract_events(text: str, file_label: str = "<text>",
                   include_warn: bool = True) -> tuple[list[LogEvent], int]:
    """(events, lines_scanned) from one log text."""
    events: list[LogEvent] = []
    current: LogEvent | None = None
    current_lines: list[str] = []
    n_lines = 0

    def close() -> None:
        nonlocal current, current_lines
        if current is not None:
            events.append(_finalize(current, current_lines))
        current, current_lines = None, []

    for line_no, line in enumerate(text.splitlines(), start=1):
        n_lines += 1
        if len(events) >= MAX_EVENTS_PER_FILE:
            break
        stripped = line.rstrip()
        if current is not None and _is_continuation(stripped):
            current_lines.append(stripped)
            continue
        level_m = _LEVEL_RE.search(stripped)
        if level_m:
            calm_m = _CALM_RE.search(stripped)
            if calm_m and calm_m.start() < level_m.start():
                close()        # an INFO line that mentions "ERROR" in text
                continue
            close()
            level = "warn" if level_m.group(1).startswith("WARN") else "error"
            ts_m = _TS_RE.search(stripped)
            message = _AFTER_LEVEL_RE.sub(
                "", stripped[level_m.end():]).strip() or stripped
            exc = ""
            exc_m = _EXC_RE.search(message)
            if exc_m:
                exc, message = exc_m.group(1), exc_m.group(2) or message
            current = LogEvent(file=file_label, line_no=line_no, level=level,
                               timestamp=ts_m.group(0) if ts_m else "",
                               exception=exc, message=message)
            current_lines = [stripped]
            continue
        # exception trace head (no log-level): belongs to the open event
        # when one exists (java logs emit the stack right after the ERROR
        # line), otherwise starts a bare-trace event (stderr dumps)
        exc_m = _EXC_RE.match(stripped)
        if exc_m and not stripped[:1].isspace() and "." in exc_m.group(1):
            if current is not None:
                current_lines.append(stripped)
                if not current.exception:
                    current.exception = exc_m.group(1)
                    current.message = exc_m.group(2) or current.message
                continue
            current = LogEvent(file=file_label, line_no=line_no,
                               level="error", exception=exc_m.group(1),
                               message=exc_m.group(2) or "")
            current_lines = [stripped]
            continue
        close()
    close()
    # filter AFTER extraction, so a skipped WARN keeps its stack trace glued
    # to itself instead of re-surfacing as a phantom bare-trace ERROR event
    if not include_warn:
        events = [e for e in events if e.level != "warn"]
    return events, n_lines


# ---------------------------------------------------------------------------
# clustering
# ---------------------------------------------------------------------------

def cluster_events(events: Iterable[LogEvent]) -> list[LogCluster]:
    clusters: dict[str, LogCluster] = {}
    for ev in events:
        sig = ev.signature
        cluster = clusters.get(sig)
        if cluster is None:
            cluster = clusters[sig] = LogCluster(
                signature=sig, level=ev.level, exception=ev.exception,
                template=normalize_message(ev.message),
                top_frame=ev.top_frame, sample=ev.raw)
        cluster.count += 1
        cluster.files[ev.file] = cluster.files.get(ev.file, 0) + 1
        if ev.level == "error":
            cluster.level = "error"    # mixed-level cluster counts as error
        if ev.timestamp:
            if not cluster.first_ts or ev.timestamp < cluster.first_ts:
                cluster.first_ts = ev.timestamp
            if not cluster.last_ts or ev.timestamp > cluster.last_ts:
                cluster.last_ts = ev.timestamp
    return sorted(clusters.values(),
                  key=lambda c: (c.level != "error", -c.count, c.signature))


# ---------------------------------------------------------------------------
# entry points
# ---------------------------------------------------------------------------

def collect_log_files(directory: str | Path,
                      patterns: Iterable[str] = DEFAULT_PATTERNS,
                      ) -> list[Path]:
    root = Path(directory)
    files: set[Path] = set()
    for pattern in patterns:
        files.update(p for p in root.rglob(pattern) if p.is_file())
    return sorted(files)


def scan_files(paths: Iterable[Path] | Iterable[str],
               include_warn: bool = True, root: str = "") -> InspectReport:
    paths = [Path(p) for p in paths]
    report = InspectReport(root=root or f"{len(paths)} files")
    all_events: list[LogEvent] = []
    for path in paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                # text mode: the cap counts characters (≈ bytes for logs)
                text = fh.read(MAX_FILE_BYTES + 1)
        except OSError as exc:
            report.warnings.append(f"无法读取 {path}: {exc}")
            continue
        if len(text) > MAX_FILE_BYTES:
            text = text[:MAX_FILE_BYTES]
            report.warnings.append(
                f"{path}: 超过单文件扫描上限，仅统计前 "
                f"{MAX_FILE_BYTES // (1024 * 1024)}MB — 计数可能偏低")
        events, n_lines = extract_events(
            text, file_label=str(path), include_warn=include_warn)
        all_events.extend(events)
        report.lines_scanned += n_lines
        report.files_scanned += 1
    report.events = len(all_events)
    report.clusters = cluster_events(all_events)
    return report


def scan_dir(directory: str | Path,
             patterns: Iterable[str] = DEFAULT_PATTERNS,
             include_warn: bool = True) -> InspectReport:
    files = collect_log_files(directory, patterns)
    if not files:
        return InspectReport(
            root=str(directory),
            warnings=[f"目录 {directory} 下没有匹配 "
                      f"{'/'.join(patterns)} 的日志文件"])
    return scan_files(files, include_warn=include_warn, root=str(directory))


def scan_text(text: str, name: str = "<inline>",
              include_warn: bool = True) -> InspectReport:
    events, n_lines = extract_events(text, file_label=name,
                                     include_warn=include_warn)
    report = InspectReport(root=name, files_scanned=1,
                           lines_scanned=n_lines, events=len(events))
    report.clusters = cluster_events(events)
    return report
