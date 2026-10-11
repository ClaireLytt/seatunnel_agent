# -*- coding: utf-8 -*-
"""Runtime skew diagnosis from Spark task metrics.

Static rules suspect skew in the SQL text and probes confirm it in the
data; this module confirms it in the *execution*: straggler tasks. Two
inputs feed one analysis:

- a Spark event log (JSON lines; plain file, ``.gz``, or a rolling
  event-log directory) — fully offline, no cluster access needed;
- a Spark History Server REST endpoint (``/api/v1``), one bounded
  ``taskSummary`` call per stage.

A stage is flagged when its slowest task is both several times the
median AND absolutely long/big enough to matter (a 3x ratio on 100 ms
tasks is noise) — the same shape as the AQE skew-join definition. Where
the event log carries SQL execution events, skewed stages are mapped
back to the SQL statement that produced them.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from .i18n import dsk, normalize_lang

# a max/median ratio only counts when the max is worth caring about
MIN_TASKS = 3
DUR_RATIO_CONFIRMED = 5.0
DUR_RATIO_SUSPECT = 3.0
DUR_MAX_CONFIRMED_MS = 30_000
DUR_MAX_SUSPECT_MS = 10_000
SHUF_RATIO_CONFIRMED = 5.0
SHUF_RATIO_SUSPECT = 3.0
SHUF_MAX_CONFIRMED = 128 * 1024 * 1024
SHUF_MAX_SUSPECT = 32 * 1024 * 1024

# REST: only the heaviest stages get a taskSummary call
MAX_REST_STAGES = 20
# rendering: worst stages first, the rest summarized in one line
TOP_STAGES = 8

_VERDICT_RANK = {"confirmed": 0, "suspect": 1, "ok": 2}


class RuntimeSkewError(ValueError):
    """Input-level failure; ``key`` is the i18n message key, ``arg`` the
    optional {err} detail (mirrors SplitKeyError)."""

    def __init__(self, key: str, arg: str = "") -> None:
        super().__init__(key)
        self.key = key
        self.arg = arg


@dataclass
class StageSkew:
    """Per-stage task-level skew measurement (durations in ms, bytes raw)."""
    stage_id: int
    name: str = ""
    tasks: int = 0
    dur_p50: float = 0.0
    dur_max: float = 0.0
    shuf_p50: float = 0.0
    shuf_max: float = 0.0
    sql_desc: str = ""

    @property
    def dur_ratio(self) -> float:
        if self.dur_max <= 0:
            return 0.0
        return self.dur_max / self.dur_p50 if self.dur_p50 > 0 else float("inf")

    @property
    def shuf_ratio(self) -> float:
        if self.shuf_max <= 0:
            return 0.0
        return self.shuf_max / self.shuf_p50 if self.shuf_p50 > 0 else float("inf")

    def verdict(self) -> str:
        """'confirmed' | 'suspect' | 'ok' — worst of duration and shuffle."""
        if self.tasks < MIN_TASKS:
            return "ok"
        v = _metric_verdict(self.dur_ratio, self.dur_max,
                            DUR_RATIO_CONFIRMED, DUR_RATIO_SUSPECT,
                            DUR_MAX_CONFIRMED_MS, DUR_MAX_SUSPECT_MS)
        w = _metric_verdict(self.shuf_ratio, self.shuf_max,
                            SHUF_RATIO_CONFIRMED, SHUF_RATIO_SUSPECT,
                            SHUF_MAX_CONFIRMED, SHUF_MAX_SUSPECT)
        return min(v, w, key=lambda x: _VERDICT_RANK[x])


def _metric_verdict(ratio: float, mx: float, r_conf: float, r_susp: float,
                    m_conf: float, m_susp: float) -> str:
    if ratio >= r_conf and mx >= m_conf:
        return "confirmed"
    if ratio >= r_susp and mx >= m_susp:
        return "suspect"
    return "ok"


def sort_stages(stages: list[StageSkew]) -> list[StageSkew]:
    """Worst first: verdict class, then duration ratio, then max duration."""
    return sorted(stages, key=lambda s: (
        _VERDICT_RANK[s.verdict()],
        -(0.0 if s.dur_ratio == float("inf") else s.dur_ratio),
        -s.dur_max))


# ---------------------------------------------------------------------------
# Event log parsing (offline)
# ---------------------------------------------------------------------------

@dataclass
class _StageAgg:
    name: str = ""
    durations: list[float] = field(default_factory=list)
    shuffle_bytes: list[float] = field(default_factory=list)


def _open_maybe_gz(path: Path):
    if path.suffix == ".gz":
        import gzip
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def _iter_eventlog_lines(path: Path):
    """Yield event-log lines from a file, a .gz file, or a Spark rolling
    event-log directory (its ``events_*`` parts, in order)."""
    if path.is_dir():
        parts = sorted(p for p in path.iterdir()
                       if p.is_file() and p.name.startswith("events"))
        if not parts:
            raise RuntimeSkewError("rt_read_fail",
                                   f"no events_* files under {path}")
        for part in parts:
            with _open_maybe_gz(part) as f:
                yield from f
        return
    with _open_maybe_gz(path) as f:
        yield from f


def parse_eventlog(path: str | Path) -> tuple[list[StageSkew], str]:
    """(stages worst-first, app label) from a Spark event log.

    Only successful task attempts count. SQL execution events, when
    present, map each skewed stage back to its SQL description."""
    p = Path(path)
    stages: dict[int, _StageAgg] = {}
    stage_to_exec: dict[int, str] = {}
    exec_desc: dict[str, str] = {}
    app_name = ""
    try:
        for raw in _iter_eventlog_lines(p):
            raw = raw.strip()
            if not raw:
                continue
            try:
                ev = json.loads(raw)
            except ValueError:
                continue  # torn/corrupt line — skip, keep scanning
            kind = str(ev.get("Event", ""))
            if kind == "SparkListenerTaskEnd":
                info = ev.get("Task Info") or {}
                if info.get("Failed") or info.get("Killed"):
                    continue
                sid = int(ev.get("Stage ID", -1))
                if sid < 0:
                    continue
                agg = stages.setdefault(sid, _StageAgg())
                launch = float(info.get("Launch Time") or 0)
                finish = float(info.get("Finish Time") or 0)
                metrics = ev.get("Task Metrics") or {}
                dur = (finish - launch if finish > launch
                       else float(metrics.get("Executor Run Time") or 0))
                agg.durations.append(dur)
                sr = metrics.get("Shuffle Read Metrics") or {}
                agg.shuffle_bytes.append(
                    float(sr.get("Remote Bytes Read") or 0)
                    + float(sr.get("Local Bytes Read") or 0))
            elif kind in ("SparkListenerStageCompleted",
                          "SparkListenerStageSubmitted"):
                si = ev.get("Stage Info") or {}
                sid = int(si.get("Stage ID", -1))
                if sid >= 0:
                    agg = stages.setdefault(sid, _StageAgg())
                    agg.name = str(si.get("Stage Name") or agg.name)
            elif kind == "SparkListenerJobStart":
                props = ev.get("Properties") or {}
                exec_id = str(props.get("spark.sql.execution.id") or "")
                if exec_id:
                    for sid in ev.get("Stage IDs") or []:
                        stage_to_exec[int(sid)] = exec_id
            elif kind.endswith("SparkListenerSQLExecutionStart"):
                exec_desc[str(ev.get("executionId"))] = \
                    str(ev.get("description") or "")
            elif kind == "SparkListenerApplicationStart":
                app_name = str(ev.get("App Name") or "")
    except OSError as exc:
        raise RuntimeSkewError("rt_read_fail", str(exc))

    out: list[StageSkew] = []
    for sid, agg in stages.items():
        if not agg.durations:
            continue
        out.append(StageSkew(
            stage_id=sid,
            name=agg.name,
            tasks=len(agg.durations),
            dur_p50=float(statistics.median(agg.durations)),
            dur_max=max(agg.durations),
            shuf_p50=float(statistics.median(agg.shuffle_bytes)),
            shuf_max=max(agg.shuffle_bytes),
            sql_desc=exec_desc.get(stage_to_exec.get(sid, ""), ""),
        ))
    if not out:
        raise RuntimeSkewError("rt_no_stages")
    return sort_stages(out), app_name or p.name


# ---------------------------------------------------------------------------
# History Server REST (online)
# ---------------------------------------------------------------------------

def _fetch_json(url: str, timeout: float = 10.0):
    import urllib.request

    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def analyze_history_server(
    base_url: str,
    app_id: str,
    fetch=_fetch_json,
    max_stages: int = MAX_REST_STAGES,
) -> tuple[list[StageSkew], str]:
    """(stages worst-first, app label) via the History Server REST API.

    One ``stages`` listing, then one ``taskSummary`` (median + max
    quantiles) per heaviest stage — bounded to *max_stages* calls."""
    base = (base_url or "").strip().rstrip("/")
    app = (app_id or "").strip()
    if not base or not app:
        raise RuntimeSkewError("rt_need_url")
    if not base.endswith("/api/v1"):
        base += "/api/v1"
    try:
        listing = fetch(f"{base}/applications/{app}/stages?status=COMPLETE")
    except Exception as exc:  # noqa: BLE001 — network/HTTP/JSON
        raise RuntimeSkewError("rt_http_fail", str(exc))
    if not isinstance(listing, list) or not listing:
        raise RuntimeSkewError("rt_no_stages")

    def _run_time(st: dict) -> float:
        try:
            return float(st.get("executorRunTime") or 0)
        except (TypeError, ValueError):
            return 0.0

    heaviest = sorted(listing, key=_run_time, reverse=True)[:max_stages]
    out: list[StageSkew] = []
    for st in heaviest:
        sid = st.get("stageId")
        if sid is None:
            continue
        attempt = st.get("attemptId", 0)
        try:
            summ = fetch(f"{base}/applications/{app}/stages/{sid}/{attempt}"
                         f"/taskSummary?quantiles=0.5,1.0")
        except Exception:  # noqa: BLE001 — one bad stage stays local
            continue
        dur = summ.get("duration") or summ.get("executorRunTime") or [0, 0]
        shuf = (summ.get("shuffleReadMetrics") or {}).get("readBytes") or [0, 0]
        out.append(StageSkew(
            stage_id=int(sid),
            name=str(st.get("name") or ""),
            tasks=int(st.get("numCompleteTasks") or st.get("numTasks") or 0),
            dur_p50=float(dur[0] or 0),
            dur_max=float(dur[-1] or 0),
            shuf_p50=float(shuf[0] or 0),
            shuf_max=float(shuf[-1] or 0),
        ))
    if not out:
        raise RuntimeSkewError("rt_no_stages")
    return sort_stages(out), app


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _fmt_ms(ms: float) -> str:
    if ms >= 60_000:
        return f"{ms / 60_000:.1f}m"
    if ms >= 1_000:
        return f"{ms / 1_000:.1f}s"
    return f"{ms:.0f}ms"


def _fmt_bytes(b: float) -> str:
    if b >= 1 << 30:
        return f"{b / (1 << 30):.1f}GB"
    if b >= 1 << 20:
        return f"{b / (1 << 20):.1f}MB"
    if b >= 1 << 10:
        return f"{b / (1 << 10):.1f}KB"
    return f"{b:.0f}B"


def _fmt_ratio(r: float) -> str:
    if r == float("inf"):
        return "∞"
    return f"{r:.1f}x"


def _stage_name(name: str, limit: int = 46) -> str:
    name = (name or "").replace("|", "\\|").replace("\n", " ").strip()
    return name if len(name) <= limit else name[:limit - 1] + "…"


def render_runtime_section(stages: list[StageSkew], lang: str,
                           source_label: str = "") -> str:
    """Bilingual '## 运行时倾斜诊断' markdown section."""
    lang = normalize_lang(lang)
    stages = sort_stages(stages)
    confirmed = sum(1 for s in stages if s.verdict() == "confirmed")
    suspect = sum(1 for s in stages if s.verdict() == "suspect")

    parts = [dsk(lang, "rt_section"), ""]
    if source_label:
        parts += [dsk(lang, "rt_source").format(src=source_label), ""]
    parts += [dsk(lang, "rt_counts").format(
        stages=len(stages), confirmed=confirmed, suspect=suspect), ""]

    shown = stages[:TOP_STAGES]
    header = (f"| Stage | {dsk(lang, 'rt_col_tasks')} | "
              f"{dsk(lang, 'rt_col_dur')} | {dsk(lang, 'rt_col_dur_ratio')} | "
              f"{dsk(lang, 'rt_col_shuf')} | {dsk(lang, 'rt_col_shuf_ratio')} | "
              f"{dsk(lang, 'rt_col_verdict')} |")
    parts += [header, "|---|---|---|---|---|---|---|"]
    for s in shown:
        parts.append(
            f"| {s.stage_id} `{_stage_name(s.name)}` | {s.tasks} | "
            f"{_fmt_ms(s.dur_p50)} → {_fmt_ms(s.dur_max)} | "
            f"{_fmt_ratio(s.dur_ratio)} | "
            f"{_fmt_bytes(s.shuf_p50)} → {_fmt_bytes(s.shuf_max)} | "
            f"{_fmt_ratio(s.shuf_ratio)} | "
            f"{dsk(lang, 'rt_verdict_' + s.verdict())} |")
    if len(stages) > len(shown):
        parts.append(dsk(lang, "rt_more_stages").format(
            n=len(stages) - len(shown)))
    parts.append("")

    # skewed stages that carry a SQL mapping (event-log path only)
    sql_lines = [
        dsk(lang, "rt_sql_map").format(
            sid=s.stage_id, sql=_stage_name(s.sql_desc, 100))
        for s in shown
        if s.verdict() != "ok" and s.sql_desc
    ]
    if sql_lines:
        parts += [dsk(lang, "rt_sql_map_head"), ""]
        parts += sql_lines
        parts.append("")

    if confirmed or suspect:
        parts += [
            dsk(lang, "rt_advice_head"), "",
            "```properties",
            "spark.sql.adaptive.enabled=true",
            "spark.sql.adaptive.skewJoin.enabled=true",
            "spark.sql.adaptive.skewJoin.skewedPartitionFactor=5",
            "spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes=256m",
            "spark.sql.adaptive.advisoryPartitionSizeInBytes=64m",
            "```", "",
            dsk(lang, "rt_advice_next"), "",
        ]
    else:
        parts += [dsk(lang, "rt_all_ok"), ""]
    return "\n".join(parts)


def check_runtime_eventlog(path: str | Path, lang: str = "zh") -> str:
    """Parse → analyze → render, for an event log file/directory."""
    stages, label = parse_eventlog(path)
    return render_runtime_section(stages, lang, source_label=label)


def check_runtime_history(base_url: str, app_id: str, lang: str = "zh",
                          fetch=_fetch_json) -> str:
    """Fetch → analyze → render, for a History Server application."""
    stages, label = analyze_history_server(base_url, app_id, fetch=fetch)
    return render_runtime_section(stages, lang, source_label=label)
