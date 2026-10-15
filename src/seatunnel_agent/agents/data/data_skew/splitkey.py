# -*- coding: utf-8 -*-
"""SeaTunnel split-key check: measure the parallel-read partition column.

Static skew rules cover the compute layer; this module covers the sync /
ingest layer. Given a SeaTunnel job config (HOCON), it resolves the JDBC
source's base table and ``partition_column``, measures that column's
distribution on the connected database (NDV / NULL ratio / top-1 share,
one bounded scan per query, sampling honored), and ranks candidate
numeric/date columns as replacement split keys — a skewed split key means
one read task drags the whole sync job.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .i18n import dsk
from seatunnel_agent.common.utils import normalize_lang
from .seatunnel_conf import (  # noqa: F401 — re-exported, public API
    SourceSpec,
    SplitKeyError,
    _spec_from_params,
    parse_seatunnel_sources,
    parse_seatunnel_source,
    _is_code_line,
    apply_split_key,
    SinkSpec,
    parse_seatunnel_sinks,
)
from .measure import (  # noqa: F401 — re-exported, public API
    _GOOD_VERDICTS,
    MAX_CANDIDATES,
    MAX_PARALLEL,
    NDV_PER_TASK,
    SplitStat,
    _ndv_expr,
    _stats_sql,
    _top1_sql,
    measure_column,
    candidate_columns,
    measure_columns,
    rank_candidates,
    pick_best_key,
)
from .probe import (
    HOT_KEY_CONFIRMED,
    HOT_KEY_SUSPECT,
    NULL_CONFIRMED,
    _pct,
    _safe_value,
)

# multi-source configs: measure at most this many sources per check
MAX_SOURCES = 3
# a split key should hold clearly more distinct values than read tasks,
# or range/hash splits collapse onto few tasks
# single-table FROM in a source query (subqueries/joins are out of scope)
# column types worth proposing as split keys: integers, decimals, dates
# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

# Approximate-NDV function per engine: an exact COUNT(DISTINCT) on a big
# table is the most expensive part of the check, and the NDV only feeds a
# threshold (>= NDV_PER_TASK * tasks), so a few % of HLL error is free money.
# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _stat_row(s: SplitStat, tasks: int, lang: str) -> str:
    verdict = dsk(lang, f"spk_verdict_{s.verdict(tasks)}") \
        if s.verdict(tasks) != "empty" else dsk(lang, "prb_verdict_empty")
    if s.error:
        err = s.error.replace("|", "\\|").replace("\n", " ")
        err = err if len(err) <= 80 else err[:79] + "…"
        return f"| `{s.column}` | - | - | - | {err} | {verdict} |"
    top1 = (f"`{_safe_value(s.top1_value)}` ({_pct(s.top1_ratio)})"
            if s.top1_count else "-")
    return (f"| `{s.column}` | {s.total} | {s.ndv} | "
            f"{_pct(s.null_ratio)} | {top1} | {verdict} |")


# a hot-share jump this big (percentage points) is reported even while the
# verdict is still fine — the patrol's early-warning signal
DRIFT_PP = 10.0


def _recheck_line(previous: dict, cur_verdict: str, lang: str,
                  cur_top1: float | None = None) -> str:
    """One-line before/after comparison against the last splitkey check of
    the same table (from history) — the loop-closing 'did the fix land?'
    signal. Quiet when both checks are fine, unless the measured top-1
    share drifted by >= DRIFT_PP points (early warning)."""
    sk = previous.get("splitkey") or {}
    pv = str(sk.get("key_verdict") or "none")
    pk = str(sk.get("partition_column") or "") or "(none)"
    ts = str(previous.get("timestamp") or "")[:16].replace("T", " ")
    prev_ok = pv in _GOOD_VERDICTS
    cur_ok = cur_verdict in _GOOD_VERDICTS
    if prev_ok and cur_ok:
        prev_top1 = sk.get("top1_pct")
        if (cur_top1 is not None and prev_top1 is not None
                and cur_top1 - float(prev_top1) >= DRIFT_PP):
            return dsk(lang, "spk_recheck_drift").format(
                ts=ts, prev=f"{float(prev_top1):.1f}", cur=f"{cur_top1:.1f}",
                delta=f"{cur_top1 - float(prev_top1):+.1f}")
        return ""
    key = ("spk_recheck_improved" if cur_ok
           else "spk_recheck_regressed" if prev_ok
           else "spk_recheck_still_bad")
    return dsk(lang, key).format(ts=ts, pk=pk, pv=pv, cv=cur_verdict)


def splitkey_metrics(configured: SplitStat | None) -> dict:
    """log_splitkey kwargs for the configured key's measured metrics
    (empty when nothing usable was measured)."""
    if configured is None or configured.error or not configured.total:
        return {}
    return {"top1_pct": configured.top1_ratio * 100,
            "ndv": configured.ndv,
            "null_pct": configured.null_ratio * 100}


def render_splitkey_section(
    spec: SourceSpec,
    configured: SplitStat | None,
    candidates: list[SplitStat],
    lang: str,
    sample_pct: int = 0,
    previous: dict | None = None,
    heading: bool = True,
) -> str:
    """Bilingual '## SeaTunnel 分片键体检（实测）' markdown section.

    *previous* is the table's last splitkey history record (or None): it
    renders as a re-check comparison line so a fixed key shows as fixed.
    *heading=False* renders the body only (no section header, no sink
    note) — the multi-source renderer stitches bodies under one header."""
    lang = normalize_lang(lang)
    zh = lang == "zh"
    tasks = spec.tasks
    parts = [dsk(lang, "spk_section"), ""] if heading else []
    src_line = (f"source `{spec.plugin}` → 表 `{spec.table}`，并行度 {tasks}"
                if zh else
                f"source `{spec.plugin}` → table `{spec.table}`, parallelism {tasks}")
    if sample_pct:
        src_line += " " + dsk(lang, "spk_sampled_note").format(pct=sample_pct)
    parts += [src_line, ""]

    header = (
        f"| {dsk(lang, 'spk_col_column')} | {dsk(lang, 'spk_col_rows')} | "
        f"{dsk(lang, 'spk_col_ndv')} | {dsk(lang, 'spk_col_null')} | "
        f"{dsk(lang, 'spk_col_top1')} | {dsk(lang, 'spk_col_verdict')} |"
    )
    sep = "|---|---|---|---|---|---|"

    if configured is not None:
        parts += [dsk(lang, "spk_configured") + f": `{spec.partition_column}`", "",
                  header, sep, _stat_row(configured, tasks, lang), ""]
    else:
        parts += [dsk(lang, "spk_none_configured"), ""]

    if previous is not None:
        cur_v = configured.verdict(tasks) if configured is not None else "none"
        cur_top1 = (configured.top1_ratio * 100
                    if configured is not None and configured.total else None)
        line = _recheck_line(previous, cur_v, lang, cur_top1=cur_top1)
        if line:
            parts += [line, ""]

    ranked = rank_candidates(candidates, tasks) if candidates else []
    if ranked:
        parts += [dsk(lang, "spk_candidates"), "", header, sep]
        parts += [_stat_row(s, tasks, lang) for s in ranked]
        parts.append("")
    elif configured is None:
        parts += [dsk(lang, "spk_no_candidates"), ""]

    # config snippet: keep a good configured key, else promote the best
    # measured candidate
    best = pick_best_key(spec, configured, candidates)
    if best is not None:
        note = ("实测 top1≈{p}，NDV={n}" if zh else "measured top1≈{p}, NDV={n}").format(
            p=_pct(best.top1_ratio), n=best.ndv)
        parts += [
            dsk(lang, "spk_snippet_head"), "",
            "```hocon",
            f"{spec.plugin or 'Jdbc'} {{",
            f"  # {note}",
            f'  partition_column = "{best.column}"',
            f"  partition_num = {max(spec.partition_num, tasks)}",
            "}",
            "```", "",
        ]
    if heading:
        parts += [dsk(lang, "spk_sink_note"), ""]
    return "\n".join(parts)


def render_splitkey_multi(
    results: list[tuple[SourceSpec, SplitStat | None, list[SplitStat]]],
    lang: str,
    sample_pct: int = 0,
    total: int = 0,
    previous_by_table: dict[str, dict] | None = None,
) -> str:
    """One report for a (possibly multi-source) check.

    A single-source result renders exactly like before; several sources
    share one section header, with each source's body separated by a rule
    and the sink note appearing once at the end. *total* is the number of
    sources parsed (may exceed ``len(results)`` when the check was capped
    at MAX_SOURCES); *previous_by_table* maps table → last history record."""
    lang = normalize_lang(lang)
    prev = previous_by_table or {}
    if len(results) == 1 and (total or 1) <= 1:
        spec, configured, candidates = results[0]
        return render_splitkey_section(
            spec, configured, candidates, lang, sample_pct=sample_pct,
            previous=prev.get(spec.table))
    note_key = ("spk_multi_truncated" if total > len(results)
                else "spk_multi_note")
    parts = [dsk(lang, "spk_section"), "",
             dsk(lang, note_key).format(n=total or len(results),
                                        shown=len(results)), ""]
    bodies = [
        render_splitkey_section(
            spec, configured, candidates, lang, sample_pct=sample_pct,
            previous=prev.get(spec.table), heading=False)
        for spec, configured, candidates in results
    ]
    parts.append("\n---\n\n".join(bodies))
    parts += [dsk(lang, "spk_sink_note"), ""]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Write-back
# ---------------------------------------------------------------------------

# an option's `= value` tail: quoted string or bare token
def _measure_source(executor, spec: SourceSpec, ds_type: str,
                    sample_pct: int) -> tuple[SourceSpec, SplitStat | None, list[SplitStat]]:
    configured = None
    if spec.partition_column:
        configured = measure_column(
            executor, spec.table, spec.partition_column, ds_type, sample_pct)
    try:
        names = candidate_columns(executor, spec.table, exclude=spec.partition_column)
    except Exception:  # noqa: BLE001 — schema listing is best-effort
        names = []
    candidates = measure_columns(executor, spec.table, names, ds_type, sample_pct)
    return spec, configured, candidates


def run_split_key(
    executor,
    conf_text: str,
    ds_type: str = "",
    sample_pct: int = 0,
) -> tuple[SourceSpec, SplitStat | None, list[SplitStat]]:
    """Parse the config and measure its first source; the single-source
    compatibility path. Raises SplitKeyError on config problems."""
    spec = parse_seatunnel_source(conf_text)
    return _measure_source(executor, spec, ds_type, sample_pct)


def run_split_key_multi(
    executor,
    conf_text: str,
    ds_type: str = "",
    sample_pct: int = 0,
    max_sources: int = MAX_SOURCES,
) -> tuple[list[tuple[SourceSpec, SplitStat | None, list[SplitStat]]], int]:
    """Parse the config and measure every source (capped at *max_sources*).

    Returns ``(results, total_sources)``; the structured half of a
    multi-source check. Raises SplitKeyError on config problems."""
    specs = parse_seatunnel_sources(conf_text)
    results = [_measure_source(executor, spec, ds_type, sample_pct)
               for spec in specs[:max_sources]]
    return results, len(specs)


def sink_key_section(
    executor,
    conf_text: str,
    ds_type: str = "",
    sample_pct: int = 0,
    lang: str = "zh",
) -> str:
    """Best-effort sink-side key sub-section ('' when there is nothing to
    measure or anything fails — it never breaks the split-key check)."""
    try:
        results, src_table = run_sink_keys(
            executor, conf_text, ds_type=ds_type, sample_pct=sample_pct)
        return render_sinkkey_section(results, src_table, lang,
                                      sample_pct=sample_pct)
    except Exception:  # noqa: BLE001 — strictly additive to the main check
        return ""


# ---------------------------------------------------------------------------
# Sink-side key check (bucket / sharding / partition keys)
# ---------------------------------------------------------------------------

# sink options that carry a data-distribution key, checked in this order;
# each present option becomes its own SinkSpec (a sink may set several)
def sink_verdict(stat: SplitStat) -> str:
    """'good' | 'suspect' | 'bad' | 'null' | 'empty' | 'error' — hot-share
    based only: unlike a split key, a sink key (e.g. a date partition_by)
    may legitimately have a low NDV."""
    if stat.error:
        return "error"
    if not stat.total:
        return "empty"
    if stat.null_ratio >= NULL_CONFIRMED:
        return "null"
    if stat.top1_ratio >= HOT_KEY_CONFIRMED:
        return "bad"
    if stat.top1_ratio >= HOT_KEY_SUSPECT:
        return "suspect"
    return "good"


def run_sink_keys(
    executor,
    conf_text: str,
    ds_type: str = "",
    sample_pct: int = 0,
) -> tuple[list[tuple[SinkSpec, list[SplitStat]]], str]:
    """Measure every sink distribution key on the FIRST source's base table
    (the rows a sink writes are the rows that source reads, so the source
    distribution is the sink key's distribution). Returns
    ``(per-sink results, source table)``; ([], "") when the config has no
    sink keys or no resolvable source."""
    try:
        source = parse_seatunnel_sources(conf_text)[0]
    except SplitKeyError:
        return [], ""
    sinks = parse_seatunnel_sinks(conf_text)
    if not sinks:
        return [], source.table
    out = []
    for spec in sinks:
        stats = measure_columns(executor, source.table, spec.columns,
                                ds_type, sample_pct)
        out.append((spec, stats))
    return out, source.table


def _sink_stat_row(s: SplitStat, lang: str) -> str:
    v = sink_verdict(s)
    verdict = (dsk(lang, f"snk_verdict_{v}") if v not in ("empty", "error")
               else dsk(lang, "prb_verdict_empty") if v == "empty"
               else dsk(lang, "spk_verdict_error"))
    if s.error:
        err = s.error.replace("|", "\\|").replace("\n", " ")
        err = err if len(err) <= 80 else err[:79] + "…"
        return f"| `{s.column}` | - | - | - | {err} | {verdict} |"
    top1 = (f"`{_safe_value(s.top1_value)}` ({_pct(s.top1_ratio)})"
            if s.top1_count else "-")
    return (f"| `{s.column}` | {s.total} | {s.ndv} | "
            f"{_pct(s.null_ratio)} | {top1} | {verdict} |")


def render_sinkkey_section(
    results: list[tuple[SinkSpec, list[SplitStat]]],
    source_table: str,
    lang: str,
    sample_pct: int = 0,
) -> str:
    """H3 sub-section (lives inside the split-key section) measuring the
    sink-side keys; '' when there is nothing to show."""
    if not results:
        return ""
    lang = normalize_lang(lang)
    parts = [dsk(lang, "snk_section"), "",
             dsk(lang, "snk_intro").format(table=source_table), ""]
    if sample_pct:
        parts += [dsk(lang, "spk_sampled_note").format(pct=sample_pct), ""]
    header = (
        f"| {dsk(lang, 'spk_col_column')} | {dsk(lang, 'spk_col_rows')} | "
        f"{dsk(lang, 'spk_col_ndv')} | {dsk(lang, 'spk_col_null')} | "
        f"{dsk(lang, 'spk_col_top1')} | {dsk(lang, 'spk_col_verdict')} |"
    )
    for spec, stats in results:
        label = f"`{spec.plugin}`"
        if spec.table:
            label += f" → `{spec.table}`"
        parts += [dsk(lang, "snk_line").format(sink=label, opt=spec.option),
                  "", header, "|---|---|---|---|---|---|"]
        parts += [_sink_stat_row(s, lang) for s in stats]
        parts.append("")
    if any(sink_verdict(s) in ("bad", "null") for _, stats in results
           for s in stats):
        parts += [dsk(lang, "snk_hot_note"), ""]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Batch mode (directory of job configs — the scheduled-patrol entry)
# ---------------------------------------------------------------------------

CONF_GLOBS = ("*.conf", "*.config", "*.hocon", "*.json")


@dataclass
class BatchFileResult:
    """One config file's check in a batch run."""
    path: str
    results: list = field(default_factory=list)  # (spec, configured, candidates)
    total: int = 0
    error_key: str = ""   # SplitKeyError key when the file failed to parse
    error_arg: str = ""

def scan_config_files(directory: str, recursive: bool = True) -> list:
    """SeaTunnel-ish config files under *directory*, sorted, de-duplicated."""
    from pathlib import Path

    root = Path(directory)
    seen: dict[str, object] = {}
    for pattern in CONF_GLOBS:
        it = root.rglob(pattern) if recursive else root.glob(pattern)
        for p in it:
            if p.is_file():
                seen[str(p)] = p
    return [seen[k] for k in sorted(seen)]


def run_split_key_batch(
    executor,
    files: list,
    ds_type: str = "",
    sample_pct: int = 0,
    max_sources: int = MAX_SOURCES,
) -> list[BatchFileResult]:
    """Check every config file; per-file failures stay local to their row."""
    out: list[BatchFileResult] = []
    for f in files:
        from pathlib import Path

        path = Path(f)
        item = BatchFileResult(path=str(path))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            item.results, item.total = run_split_key_multi(
                executor, text, ds_type=ds_type, sample_pct=sample_pct,
                max_sources=max_sources)
        except SplitKeyError as exc:
            item.error_key, item.error_arg = exc.key, exc.arg
        except Exception as exc:  # noqa: BLE001 — one broken file stays local
            item.error_key, item.error_arg = "spk_parse_fail", str(exc)
        out.append(item)
    return out


_BAD_VERDICTS = ("bad", "low_ndv", "null")


def batch_counts(items: list[BatchFileResult]) -> dict:
    """{'files', 'sources', 'bad', 'none', 'errors'} across a batch run."""
    sources = bad = none = 0
    errors = sum(1 for it in items if it.error_key)
    for it in items:
        for spec, configured, _ in it.results:
            sources += 1
            v = configured.verdict(spec.tasks) if configured else "none"
            if v in _BAD_VERDICTS:
                bad += 1
            elif v == "none":
                none += 1
    return {"files": len(items), "sources": sources, "bad": bad,
            "none": none, "errors": errors}


def render_splitkey_batch(items: list[BatchFileResult], lang: str,
                          sample_pct: int = 0) -> str:
    """One summary table for a directory patrol — a row per source, an
    error row per unparsable file, counts up front."""
    from pathlib import Path

    lang = normalize_lang(lang)
    c = batch_counts(items)
    parts = [dsk(lang, "spk_batch_section"), "",
             dsk(lang, "spk_batch_counts").format(**c), ""]
    if sample_pct:
        parts += [dsk(lang, "spk_sampled_note").format(pct=sample_pct), ""]

    header = (f"| {dsk(lang, 'spk_batch_col_file')} | "
              f"{dsk(lang, 'spk_batch_col_table')} | "
              f"{dsk(lang, 'spk_batch_col_key')} | "
              f"{dsk(lang, 'spk_col_verdict')} | "
              f"{dsk(lang, 'spk_batch_col_best')} |")
    parts += [header, "|---|---|---|---|---|"]
    for it in items:
        name = Path(it.path).name
        if it.error_key:
            err = dsk(lang, it.error_key).format(err=it.error_arg)
            err = err.replace("|", "\\|").replace("\n", " ")
            err = err if len(err) <= 70 else err[:69] + "…"
            parts.append(f"| `{name}` | - | - | {err} | - |")
            continue
        for spec, configured, candidates in it.results:
            v = configured.verdict(spec.tasks) if configured else "none"
            verdict = (dsk(lang, f"spk_verdict_{v}") if v != "none"
                       else dsk(lang, "spk_batch_no_key"))
            best = pick_best_key(spec, configured, candidates)
            best_cell = "-"
            if best is not None and best.column != spec.partition_column:
                best_cell = f"`{best.column}`"
            elif best is not None:
                best_cell = dsk(lang, "spk_batch_keep")
            key = f"`{spec.partition_column}`" if spec.partition_column else "-"
            parts.append(f"| `{name}` | `{spec.table}` | {key} | "
                         f"{verdict} | {best_cell} |")
    parts += ["", dsk(lang, "spk_batch_hint"), ""]
    return "\n".join(parts)
