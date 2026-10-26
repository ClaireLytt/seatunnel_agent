"""Scheduled query subscriptions with Feishu card push (PRD §6 / M4).

A subscription = data source (a defined metric, or a saved favorite with
``${param}`` placeholders) + a 5-field cron + a Feishu incoming-webhook URL.
The scheduler ticks in a daemon thread; due subscriptions run through the
same validator / LIMIT / whitelist stack as interactive queries and push a
result card (≤10 rows) — failures push an error summary card, so silence
never means success.

Zero new dependencies: the cron matcher (standard 5 fields: minute hour
day-of-month month day-of-week, supporting ``*``, ``*/n``, ``a-b``,
``a,b,c`` and ``a-b/n``) and the Feishu webhook call (stdlib urllib) are
both self-contained.

Security: connections are resolved server-side — a preset name (encrypted
store shared with the Data Comparison page) or environment variables —
never credentials stored in the subscription itself. Cards carry only the
aggregated preview, not detail CSVs.
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from seatunnel_agent.common.filelock import file_lock
from seatunnel_agent.common.utils import (
    read_json_list,
    read_json_list_strict,
    write_json_atomic,
)

from .attribution import NULL_LABEL
from .cron import (  # noqa: F401 — re-exported, public API
    CronSpec,
    builtin_params,
    parse_cron,
)
from .executor import DatabaseConfig, config_from_env, create_executor
from .favorites import FavoritesStore, apply_params
from .metrics import (
    MetricError,
    MetricStore,
    build_metric_sql,
    load_metric_store,
    parse_date,
    ratio_sides,
)
from .notify import (  # noqa: F401 — re-exported, public API
    _CHANNEL_PUSHERS,
    _chart_png,
    _feishu_tenant_token,
    _post_json,
    detect_channel,
    push_card,
    push_dingtalk,
    push_email,
    push_feishu,
    push_wecom,
    render_card_markdown,
    upload_feishu_image,
)
from .partition import TimeRange
from .schema import SchemaStore
from .validator import enforce_limit, validate_sql

logger = logging.getLogger(__name__)

_MAX_SUBSCRIPTIONS = 100
_CARD_MAX_ROWS = 10

SOURCE_TYPES = ("metric", "favorite", "metric_watch", "freshness", "digest")
#: digest cards cap: 2 SQL per metric must stay a bounded morning cost
_DIGEST_MAX_METRICS = 10

#: metric_watch comparison modes: dod = 昨天 vs 前天, wow = 昨天 vs 上周同日
WATCH_MODES = ("dod", "wow", "model")
#: model mode fits the forecast baseline on this many trailing days
_MODEL_HISTORY_DAYS = 28


# ----------------------------------------------------------------------
# Store (same atomic-JSON pattern as favorites)
# ----------------------------------------------------------------------


class SubscriptionStore:
    def __init__(self, path: str | Path | None = None,
                 lock_timeout: float = 10.0) -> None:
        if path is None:  # env read at init time so tests can redirect it
            path = os.getenv("T2S_SUBSCRIPTIONS_PATH", "config/t2s_subscriptions.json")
        self.path = Path(path)
        self._lock = threading.Lock()
        self._lock_timeout = lock_timeout

    def _write_lock(self):
        """Cross-process guard for every read-modify-write (CLI ``cron
        serve`` and the hub UI may write the same file concurrently).
        Reads stay lock-free/tolerant."""
        return file_lock(self.path, timeout=self._lock_timeout)

    def _read(self) -> list[dict[str, Any]]:
        return read_json_list(self.path)

    def _read_for_write(self) -> list[dict[str, Any]]:
        """Strict read used before every read-modify-write: a corrupt backing
        file raises instead of being treated as empty, so the subsequent
        write can never silently wipe existing subscriptions."""
        return read_json_list_strict(self.path)

    def _write(self, data: list[dict[str, Any]]) -> None:
        write_json_atomic(self.path, data)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read()

    def get(self, sub_id: str) -> dict[str, Any] | None:
        for entry in self.list():
            if entry.get("id") == sub_id:
                return entry
        return None

    def add(
        self,
        name: str,
        cron: str,
        source_type: str,
        *,
        metric: str = "",
        dimensions: list[str] | None = None,
        lookback_days: int = 1,
        favorite_id: str = "",
        params: dict[str, str] | None = None,
        threshold_pct: float = 10.0,
        watch_mode: str = "dod",
        max_lag_days: int = 1,
        metrics: list[str] | None = None,
        ds_type: str = "hive",
        connection: str = "",
        database: str = "",
        webhook_url: str = "",
        lang: str = "zh",
    ) -> dict[str, Any]:
        if not name.strip():
            raise ValueError("订阅名称不能为空")
        parse_cron(cron)  # validate early
        if source_type not in SOURCE_TYPES:
            raise ValueError(f"source_type 只支持 {', '.join(SOURCE_TYPES)}")
        if source_type in ("metric", "metric_watch", "freshness") and not metric.strip():
            raise ValueError(f"{source_type} 订阅必须给出指标名")
        if max_lag_days < 1:
            raise ValueError("max_lag_days 必须 >= 1")
        metrics_list = [m.strip() for m in (metrics or []) if m.strip()]
        if source_type == "digest" and len(metrics_list) > _DIGEST_MAX_METRICS:
            raise ValueError(f"digest 订阅最多 {_DIGEST_MAX_METRICS} 个指标")
        if watch_mode not in WATCH_MODES:
            raise ValueError(f"watch_mode 只支持 {', '.join(WATCH_MODES)}")
        if threshold_pct <= 0:
            raise ValueError("threshold_pct 必须 > 0")
        if source_type == "favorite" and not favorite_id.strip():
            raise ValueError("favorite 订阅必须给出收藏 ID")
        if lookback_days < 1:
            raise ValueError("lookback_days 必须 >= 1")
        entry: dict[str, Any] = {
            "id": uuid.uuid4().hex[:12],
            "name": name.strip(),
            "cron": cron.strip(),
            "source_type": source_type,
            "metric": metric.strip(),
            "dimensions": list(dimensions or []),
            "lookback_days": lookback_days,
            "favorite_id": favorite_id.strip(),
            "params": dict(params or {}),
            "threshold_pct": float(threshold_pct),
            "watch_mode": watch_mode,
            "max_lag_days": int(max_lag_days),
            "metrics": metrics_list,
            "ds_type": ds_type,
            "connection": connection.strip(),
            "database": database.strip(),
            "webhook_url": webhook_url.strip(),
            "lang": lang,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "last_run_at": "",
            "last_status": "",
            "last_error": "",
        }
        with self._lock, self._write_lock():
            data = self._read_for_write()
            data.append(entry)
            if len(data) > _MAX_SUBSCRIPTIONS:
                data = data[-_MAX_SUBSCRIPTIONS:]
            self._write(data)
        return entry

    def delete(self, sub_id: str) -> bool:
        with self._lock, self._write_lock():
            data = self._read_for_write()
            before = len(data)
            data = [e for e in data if e.get("id") != sub_id]
            if len(data) < before:
                self._write(data)
                return True
            return False

    def set_enabled(self, sub_id: str, enabled: bool) -> bool:
        with self._lock, self._write_lock():
            data = self._read_for_write()
            for entry in data:
                if entry.get("id") == sub_id:
                    entry["enabled"] = bool(enabled)
                    self._write(data)
                    return True
            return False

    def record_run(self, sub_id: str, status: str, error: str = "") -> None:
        with self._lock, self._write_lock():
            data = self._read_for_write()
            for entry in data:
                if entry.get("id") == sub_id:
                    entry["last_run_at"] = datetime.now(timezone.utc).isoformat(
                        timespec="seconds"
                    )
                    entry["last_status"] = status
                    entry["last_error"] = error[:500]
                    self._write(data)
                    return

    def record_alert_state(self, sub_id: str, state: dict[str, Any]) -> None:
        """Persist a watch subscription's alert memory (repeat suppression)."""
        with self._lock, self._write_lock():
            data = self._read_for_write()
            for entry in data:
                if entry.get("id") == sub_id:
                    entry["alert_state"] = dict(state)
                    self._write(data)
                    return


# ----------------------------------------------------------------------
# Running a subscription
# ----------------------------------------------------------------------


def resolve_db_config(sub: dict[str, Any]) -> DatabaseConfig | None:
    """Resolve the connection server-side: preset name > sqlite path > env."""
    ds_type = sub.get("ds_type", "hive")
    preset_name = (sub.get("connection") or "").strip()
    if preset_name:
        from seatunnel_agent.agents.data.data_comparison.presets import PresetsStore

        preset = PresetsStore().get_by_name(preset_name)
        if preset is None:
            return None
        return DatabaseConfig(
            ds_type=preset.get("ds_type", ds_type),
            host=preset.get("host", ""),
            port=int(preset.get("port", 0) or 0),
            database=preset.get("database", ""),
            username=preset.get("username") or None,
            password=preset.get("password") or None,
        )
    if ds_type == "sqlite":
        return DatabaseConfig(
            ds_type="sqlite", host="", port=0,
            database=sub.get("database", ""),
        )
    return config_from_env(ds_type)


def _build_subscription_sql(
    sub: dict[str, Any],
    schema_store: SchemaStore,
    metric_store: MetricStore,
    today: date | None = None,
    favorites: FavoritesStore | None = None,
) -> str:
    today = today or date.today()
    if sub.get("source_type") == "metric":
        metric = metric_store.get(sub.get("metric", ""))
        if metric is None:
            raise MetricError(f"指标 '{sub.get('metric')}' 未定义")
        lookback = int(sub.get("lookback_days", 1) or 1)
        end = today - timedelta(days=1)
        start = today - timedelta(days=lookback)
        return build_metric_sql(
            metric, metric_store, schema_store,
            dimensions=sub.get("dimensions") or [],
            time_range=TimeRange(start=start, end=end),
        )

    favorites = favorites or FavoritesStore()
    fav = next(
        (f for f in favorites.list() if f.get("id") == sub.get("favorite_id")),
        None,
    )
    if fav is None:
        raise MetricError(f"收藏 '{sub.get('favorite_id')}' 不存在")
    values = builtin_params(today)
    values.update({k: str(v) for k, v in (sub.get("params") or {}).items()})
    try:
        return apply_params(fav["sql"], values)
    except ValueError as exc:
        raise MetricError(str(exc))


def _max_time_value(
    metric, metric_store: MetricStore, schema_store: SchemaStore,
    executor, ds_type: str,
):
    """MAX(time_column) per underlying table of *metric* (both ratio sides).

    Returns {table: date|None}; raises MetricError when a side has no
    time_column.
    """
    sides = list(ratio_sides(metric, metric_store)) if metric.is_ratio else [metric]
    out: dict[str, Any] = {}
    for side in sides:
        if not side.time_column:
            raise MetricError(f"指标 '{side.name}' 没有 time_column,无法判断新鲜度")
        sql = f"SELECT MAX({side.time_column}) AS max_dt FROM {side.table}"
        validation = validate_sql(sql, schema_store)
        if not validation.ok:
            raise MetricError("SQL rejected: " + "; ".join(validation.errors))
        result = executor.run(enforce_limit(sql, dialect=ds_type), max_rows=10)
        raw = result.rows[0][0] if result.rows else None
        out[side.table] = (
            None if raw is None else parse_date(str(raw).strip()[:10])
        )
    return out


def _run_freshness(
    sub: dict[str, Any],
    schema_store: SchemaStore,
    metric_store: MetricStore,
    executor,
    today: date,
    push_fn: Callable[..., tuple[bool, str]],
) -> dict[str, Any]:
    """Data-freshness watch: alert when MAX(time_column) lags more than
    max_lag_days behind today (1 tiny SQL per underlying table)."""
    name = sub.get("name", "?")
    webhook = (sub.get("webhook_url") or "").strip()
    metric = metric_store.get(sub.get("metric", ""))
    if metric is None:
        raise MetricError(f"指标 '{sub.get('metric')}' 未定义")
    max_lag = int(sub.get("max_lag_days", 1))
    expected = today - timedelta(days=max_lag)

    max_by_table = _max_time_value(
        metric, metric_store, schema_store, executor,
        sub.get("ds_type", "hive"),
    )
    stale = {
        t: d for t, d in max_by_table.items() if d is None or d < expected
    }
    outcome: dict[str, Any] = {
        "status": "alerted" if stale else "fresh",
        "error": "", "sql": "",
        "max_by_table": {
            t: (d.isoformat() if d else None) for t, d in max_by_table.items()
        },
        "max_lag_days": max_lag,
        "expected_min_day": expected.isoformat(),
    }
    if not stale:
        return outcome  # fresh — silence by design
    lines = [
        f"- {t}: 最新 {d.isoformat() if d else '无数据'}"
        f"（要求 ≥ {expected.isoformat()}）"
        for t, d in stale.items()
    ]
    body = (
        f"**{metric.display_name}** 数据断更告警"
        f"（允许滞后 {max_lag} 天）\n" + "\n".join(lines)
    )
    if webhook:
        pushed, msg = push_fn(webhook, f"⏰ {name}", body, ok=False)
        if not pushed:
            outcome["status"] = "push_failed"
            outcome["error"] = msg
    return outcome


def _run_metric_watch(
    sub: dict[str, Any],
    schema_store: SchemaStore,
    metric_store: MetricStore,
    executor,
    today: date,
    push_fn: Callable[..., tuple[bool, str]],
) -> dict[str, Any]:
    """Anomaly-watch subscription: compare yesterday against the reference
    period; push an alert card ONLY when |change| crosses the threshold.
    Deterministic math, LLM-free."""
    name = sub.get("name", "?")
    webhook = (sub.get("webhook_url") or "").strip()
    metric = metric_store.get(sub.get("metric", ""))
    if metric is None:
        raise MetricError(f"指标 '{sub.get('metric')}' 未定义")

    yesterday = today - timedelta(days=1)
    # drilldown reference: wow and model compare the same weekday last week
    # (seasonally comparable); dod compares the previous day
    ref = yesterday - timedelta(
        days=7 if sub.get("watch_mode") in ("wow", "model") else 1,
    )
    ds_type = sub.get("ds_type", "hive")

    def _run_day_sql(day: date, max_rows: int, dimensions=None):
        """build -> validate -> LIMIT -> execute, one day's metric SQL."""
        sql = build_metric_sql(
            metric, metric_store, schema_store, dimensions=dimensions,
            time_range=TimeRange(start=day, end=day),
        )
        validation = validate_sql(sql, schema_store)
        if not validation.ok:
            raise MetricError("SQL rejected: " + "; ".join(validation.errors))
        return executor.run(enforce_limit(sql, dialect=ds_type), max_rows=max_rows)

    def _total(day: date) -> float | None:
        result = _run_day_sql(day, max_rows=10)
        if not result.rows or result.rows[0][-1] is None:
            # additive: no rows means 0; a NULL ratio (denominator 0 or no
            # data) is UNDEFINED, not 0 — coercing it would fire a false
            # "-100%" alert
            return None if metric.is_ratio else 0.0
        return float(result.rows[0][-1])

    threshold = float(sub.get("threshold_pct", 10.0))
    mode = str(sub.get("watch_mode") or "dod")

    def _no_data(note: str, prev_val: float | None = None) -> dict[str, Any]:
        return {
            "status": "no_data", "error": "", "sql": "",
            "curr": None, "prev": prev_val, "delta": None,
            "change_rate_pct": None,
            "threshold_pct": threshold,
            "curr_day": yesterday.isoformat(), "ref_day": ref.isoformat(),
            "note": note,
        }

    band: dict[str, float] | None = None
    if mode == "model":
        # forecast baseline: alert when yesterday falls outside the fitted
        # 95% interval (trend + weekday + CN-holiday aware; no fixed
        # threshold so weekend/holiday swings stop false-alerting)
        from .forecast import forecast_series
        from .metrics import build_metric_series_sql

        series_sql = build_metric_series_sql(
            metric, metric_store, schema_store,
            TimeRange(start=yesterday - timedelta(days=_MODEL_HISTORY_DAYS),
                      end=yesterday),
        )
        validation = validate_sql(series_sql, schema_store)
        if not validation.ok:
            raise MetricError("SQL rejected: " + "; ".join(validation.errors))
        s_result = executor.run(
            enforce_limit(series_sql, dialect=ds_type), max_rows=1000,
        )
        by_day: dict[date, float | None] = {}
        for r in s_result.rows:
            if r[0] is None:
                continue
            d = parse_date(str(r[0]).strip()[:10])
            by_day[d] = None if r[-1] is None else float(r[-1])
        curr = by_day.get(yesterday)
        if curr is None:
            if metric.is_ratio:
                return _no_data("比率在该日无定义（分母为 0 或无数据），跳过告警")
            # a missing day is only a true 0 when the table HAS data through
            # yesterday; a lagging pipeline must not fire a fake -100% alert
            try:
                max_by_table = _max_time_value(
                    metric, metric_store, schema_store, executor, ds_type,
                )
            except MetricError:
                max_by_table = {}
            lagging = {
                t: d for t, d in max_by_table.items()
                if d is None or d < yesterday
            }
            if lagging:
                latest = ", ".join(
                    f"{t} 最新 {d.isoformat() if d else '无数据'}"
                    for t, d in lagging.items()
                )
                return _no_data(f"数据未更新至昨日（{latest}），跳过告警")
            curr = 0.0
        history = [(d, v) for d, v in by_day.items() if d < yesterday]
        try:
            fc = forecast_series(
                history,
                horizon=(yesterday - max(d for d, _ in history)).days
                if history else 1,
                fill="ffill" if metric.is_ratio else "zero",
            )
        except ValueError as exc:
            return _no_data(f"历史不足，无法拟合基线: {exc}")
        row = next(
            (f for f in fc["forecasts"] if f["day"] == yesterday.isoformat()),
            None,
        )
        if row is None:
            return _no_data("预测基线未覆盖昨日，跳过告警")
        band = {"yhat": row["yhat"], "lo": row["lo"], "hi": row["hi"]}
        prev = float(row["yhat"])
        delta = curr - prev
        rate = (delta / abs(prev)) if prev else None
        triggered = curr < band["lo"] or curr > band["hi"]
    else:
        curr, prev = _total(yesterday), _total(ref)
        if curr is None or prev is None:
            return _no_data(
                "比率在该日无定义（分母为 0 或无数据），跳过告警", prev,
            )
        if curr == 0.0 and not metric.is_ratio:
            # "no rows yesterday" and "a true 0" look identical here; probe
            # table freshness so a lagging pipeline reports an outage
            # instead of a fake -100% alert (same guard as model mode)
            try:
                lagging = {
                    t: d for t, d in _max_time_value(
                        metric, metric_store, schema_store, executor, ds_type,
                    ).items() if d is None or d < yesterday
                }
            except MetricError:
                lagging = {}
            if lagging:
                latest = ", ".join(
                    f"{t} 最新 {d.isoformat() if d else '无数据'}"
                    for t, d in lagging.items()
                )
                return _no_data(f"数据未更新至昨日（{latest}），跳过告警", prev)
        delta = curr - prev
        rate = (delta / abs(prev)) if prev else None
        triggered = (abs(rate) * 100 >= threshold) if rate is not None else curr != 0

    outcome: dict[str, Any] = {
        "status": "alerted" if triggered else "no_change",
        "error": "",
        "sql": "",
        "curr": curr, "prev": prev, "delta": delta,
        "change_rate_pct": round(rate * 100, 2) if rate is not None else None,
        "threshold_pct": threshold,
        "curr_day": yesterday.isoformat(), "ref_day": ref.isoformat(),
    }
    if band is not None:
        outcome["baseline"] = band

    # alert memory: a persisting anomaly pushes once (first day), the same-
    # direction repeat is suppressed, and the return to normal pushes one
    # green recovery card — three cards for a three-day incident, not four
    state = dict(sub.get("alert_state") or {})
    direction = "up" if delta > 0 else "down"
    unit = f" {metric.unit}" if metric.unit else ""
    if not triggered:
        if state.get("active"):
            outcome["status"] = "recovered"
            outcome["alert_state"] = {}
            since = state.get("since", "?")
            body = (
                f"**{metric.display_name}** 异动已恢复\n"
                f"{yesterday.isoformat()}: {curr:,.2f}{unit} 回到正常区间"
                f"（自 {since} 起告警）"
            )
            if webhook:
                pushed, msg = push_fn(webhook, f"✅ {name}", body, ok=True)
                if not pushed:
                    outcome["status"] = "push_failed"
                    outcome["error"] = msg
            return outcome
        return outcome  # silence by design — no card below the threshold
    if state.get("active") and state.get("direction") == direction:
        outcome["status"] = "suppressed"
        outcome["alert_state"] = state  # keep the original 'since'
        return outcome  # same incident, already alerted — no repeat card
    outcome["alert_state"] = {
        "active": True, "direction": direction,
        "since": yesterday.isoformat(),
    }

    # top contributors on the first allowed dimension (best-effort).
    # Ratio metrics have no dimensions of their own: fall back to the
    # numerator∩denominator intersection build_metric_sql would accept.
    allowed_dims = list(metric.dimensions)
    if metric.is_ratio and not allowed_dims:
        try:
            num, den = ratio_sides(metric, metric_store)
        except MetricError:
            pass  # breakdown is best-effort; the totals already alerted
        else:
            den_set = {d.lower() for d in den.dimensions}
            allowed_dims = [d for d in num.dimensions if d.lower() in den_set]
    top_lines = ""
    dim = (sub.get("dimensions") or allowed_dims[:1] or [None])[0]
    if dim and not metric.is_ratio:
        # additive: full attribution on the alert dimension — contribution
        # percentages sum to the total change rate (identity-checked), and
        # new/gone members are marked. The alert card answers "why" itself.
        try:
            from .attribution import run_attribution

            def _exec(sql: str) -> tuple[list[str], list[tuple]]:
                validation = validate_sql(sql, schema_store)
                if not validation.ok:
                    raise MetricError(
                        "SQL rejected: " + "; ".join(validation.errors))
                result = executor.run(
                    enforce_limit(sql, dialect=ds_type), max_rows=1000,
                )
                return result.columns, result.rows

            attri = run_attribution(
                metric, metric_store, schema_store, _exec,
                curr_range=TimeRange(start=yesterday, end=yesterday),
                prev_range=TimeRange(start=ref, end=ref),
                dimensions=[dim],
            )
            rows = attri.dimensions[0].rows[:3] if attri.dimensions else []
            parts = []
            contributors = []
            for row in rows:
                mark = "（新增）" if row.is_new else "（消失）" if row.is_gone else ""
                pct = (
                    f"，贡献 {row.contribution * 100:+.1f}%"
                    if row.contribution is not None else ""
                )
                parts.append(f"- {row.value}{mark}: {row.delta:+,.2f}{pct}")
                contributors.append({
                    "value": row.value, "delta": round(row.delta, 4),
                    "contribution_pct": (
                        round(row.contribution * 100, 2)
                        if row.contribution is not None else None
                    ),
                })
            if parts:
                top_lines = "\n" + "\n".join(parts)
                outcome["top_contributors"] = contributors
        except Exception:
            pass  # contributors are a bonus
    elif dim:
        # ratio: per-member deltas are informative but not additive
        # contributions — keep the plain two-day comparison
        try:
            def _by_dim(day: date) -> dict[str, float]:
                result = _run_day_sql(day, max_rows=1000, dimensions=[dim])
                return {
                    (NULL_LABEL if r[0] is None else str(r[0])):
                        float(r[-1]) if r[-1] is not None else 0.0
                    for r in result.rows
                }

            c_map, p_map = _by_dim(yesterday), _by_dim(ref)
            deltas = sorted(
                ((k, c_map.get(k, 0.0) - p_map.get(k, 0.0))
                 for k in set(c_map) | set(p_map)),
                key=lambda kv: abs(kv[1]), reverse=True,
            )[:3]
            top_lines = "\n" + "\n".join(
                f"- {k}: {d:+,.2f}" for k, d in deltas
            )
            outcome["top_contributors"] = [
                {"value": k, "delta": round(d, 4)} for k, d in deltas
            ]
        except Exception:
            pass  # contributors are a bonus

    rate_txt = f"{rate * 100:+.2f}%" if rate is not None else "N/A(基期为0)"
    unit = f" {metric.unit}" if metric.unit else ""
    # per-dim deltas of a ratio are informative but not additive contributions
    label = "各维度变化" if metric.is_ratio else "主要贡献"
    contributor_block = f"\n{label} ({dim}):{top_lines}" if top_lines else ""
    if band is not None:
        body = (
            f"**{metric.display_name}** 异动告警（模型基线 95% 区间外）\n"
            f"{yesterday.isoformat()} 实际 {curr:,.2f}{unit}，"
            f"预期 {band['yhat']:,.2f}{unit} "
            f"[{band['lo']:,.2f}, {band['hi']:,.2f}]\n"
            f"偏离 {delta:+,.2f}{unit} ({rate_txt})" + contributor_block
        )
    else:
        body = (
            f"**{metric.display_name}** 异动告警（阈值 ±{threshold:g}%）\n"
            f"{ref.isoformat()}: {prev:,.2f}{unit} → "
            f"{yesterday.isoformat()}: {curr:,.2f}{unit}\n"
            f"变动 {delta:+,.2f}{unit} ({rate_txt})" + contributor_block
        )
    if webhook:
        pushed, msg = push_fn(webhook, f"⚠️ {name}", body, ok=False)
        if not pushed:
            outcome["status"] = "push_failed"
            outcome["error"] = msg
    return outcome


def _run_digest(
    sub: dict[str, Any],
    schema_store: SchemaStore,
    metric_store: MetricStore,
    executor,
    today: date,
    push_fn: Callable[..., tuple[bool, str]],
) -> dict[str, Any]:
    """Morning digest card: one line per metric — yesterday's value, DoD
    change, and month-target completion when declared. ≤2 SQL per metric,
    deterministic, LLM-free."""
    from .metrics import build_metric_series_sql

    name = sub.get("name", "?")
    webhook = (sub.get("webhook_url") or "").strip()
    names = list(sub.get("metrics") or []) or [
        m.name for m in metric_store.metrics
    ]
    names = names[:_DIGEST_MAX_METRICS]
    yesterday = today - timedelta(days=1)
    ds_type = sub.get("ds_type", "hive")

    def _run(sql: str, max_rows: int = 10):
        validation = validate_sql(sql, schema_store)
        if not validation.ok:
            raise MetricError("SQL rejected: " + "; ".join(validation.errors))
        return executor.run(enforce_limit(sql, dialect=ds_type), max_rows=max_rows)

    lines: list[str] = []
    rows_out: list[dict[str, Any]] = []
    for mname in names:
        metric = metric_store.get(mname)
        if metric is None:
            lines.append(f"- {mname}: 未定义")
            rows_out.append({"metric": mname, "error": "未定义"})
            continue
        try:
            series_sql = build_metric_series_sql(
                metric, metric_store, schema_store,
                TimeRange(start=yesterday - timedelta(days=1), end=yesterday),
            )
            result = _run(series_sql)
            by_day: dict[date, float] = {}
            for r in result.rows:
                if r[0] is None or r[-1] is None:
                    continue
                by_day[parse_date(str(r[0]).strip()[:10])] = float(r[-1])
            curr = by_day.get(yesterday)
            prev = by_day.get(yesterday - timedelta(days=1))
            if curr is None and not metric.is_ratio:
                curr = 0.0
            if prev is None and not metric.is_ratio:
                prev = 0.0
        except Exception as exc:  # per-line best effort: one bad metric must not kill the card
            lines.append(f"- {metric.display_name}: 查询失败")
            rows_out.append({"metric": mname, "error": str(exc)})
            continue
        unit = f" {metric.unit}" if metric.unit else ""
        if curr is None:
            line = f"- {metric.display_name}: 无数据"
            rows_out.append({"metric": mname, "curr": None})
            lines.append(line)
            continue
        dod_txt = ""
        dod_pct = None
        if prev is not None and prev != 0:
            dod_pct = round((curr - prev) / abs(prev) * 100, 2)
            dod_txt = f"（环比 {dod_pct:+.1f}%）"
        line = f"- {metric.display_name}: {curr:,.2f}{unit}{dod_txt}"
        target = metric.targets.get("month")
        completion = None
        if target:
            try:
                mtd_sql = build_metric_sql(
                    metric, metric_store, schema_store,
                    time_range=TimeRange(
                        start=yesterday.replace(day=1), end=yesterday,
                    ),
                )
                mtd_result = _run(mtd_sql)
                mtd = (
                    float(mtd_result.rows[0][-1])
                    if mtd_result.rows and mtd_result.rows[0][-1] is not None
                    else 0.0
                )
                completion = round(mtd / target * 100, 1)
                line += f" · 月目标达成 {completion:g}%"
            except Exception:
                pass  # the digest line still carries value + DoD
        lines.append(line)
        rows_out.append({
            "metric": mname, "curr": round(curr, 4),
            "dod_pct": dod_pct, "month_completion_pct": completion,
        })

    body = f"**经营日报** {yesterday.isoformat()}\n" + "\n".join(lines)
    outcome: dict[str, Any] = {
        "status": "success", "error": "", "sql": "",
        "day": yesterday.isoformat(), "rows": rows_out,
    }
    if webhook:
        pushed, msg = push_fn(webhook, f"📊 {name}", body, ok=True)
        if not pushed:
            outcome["status"] = "push_failed"
            outcome["error"] = msg
    return outcome


def backtest_watch(
    sub: dict[str, Any],
    schema_store: SchemaStore,
    metric_store: MetricStore,
    executor,
    end: date,
    days: int = 90,
) -> dict[str, Any]:
    """Replay a metric_watch subscription's alert rule over history: which
    days WOULD have alerted. One series SQL, pure-python replay — lets the
    user tune threshold/watch_mode before the subscription goes live."""
    from .forecast import forecast_series
    from .metrics import build_metric_series_sql

    metric = metric_store.get(sub.get("metric", ""))
    if metric is None:
        raise MetricError(f"指标 '{sub.get('metric')}' 未定义")
    mode = str(sub.get("watch_mode") or "dod")
    threshold = float(sub.get("threshold_pct", 10.0))
    days = max(7, min(days, 365))
    eval_start = end - timedelta(days=days - 1)
    warmup = _MODEL_HISTORY_DAYS if mode == "model" else 7
    start = eval_start - timedelta(days=warmup)

    series_sql = build_metric_series_sql(
        metric, metric_store, schema_store, TimeRange(start=start, end=end),
    )
    validation = validate_sql(series_sql, schema_store)
    if not validation.ok:
        raise MetricError("SQL rejected: " + "; ".join(validation.errors))
    result = executor.run(
        enforce_limit(series_sql, default_limit=100000,
                      dialect=sub.get("ds_type", "hive")),
        max_rows=100000,
    )
    by_day: dict[date, float | None] = {}
    for r in result.rows:
        if r[0] is None:
            continue
        by_day[parse_date(str(r[0]).strip()[:10])] = (
            None if r[-1] is None else float(r[-1])
        )

    def _val(d: date) -> float | None:
        v = by_day.get(d)
        if v is None:
            return None if metric.is_ratio else 0.0
        return v

    alerts: list[dict[str, Any]] = []
    no_data_days = 0
    evaluated = 0
    for i in range(days):
        d = eval_start + timedelta(days=i)
        curr = _val(d)
        if curr is None:
            no_data_days += 1
            continue
        if mode == "model":
            history = [
                (dd, by_day.get(dd))
                for dd in (
                    d - timedelta(days=k)
                    for k in range(_MODEL_HISTORY_DAYS, 0, -1)
                )
            ]
            try:
                observed = [(dd, v) for dd, v in history if v is not None]
                last = max(dd for dd, _ in observed) if observed else None
                fc = forecast_series(
                    history,
                    horizon=(d - last).days if last else 1,
                    fill="ffill" if metric.is_ratio else "zero",
                )
            except ValueError:
                no_data_days += 1
                continue
            row = next(
                (f for f in fc["forecasts"] if f["day"] == d.isoformat()),
                None,
            )
            if row is None:
                no_data_days += 1
                continue
            evaluated += 1
            if curr < row["lo"] or curr > row["hi"]:
                alerts.append({
                    "day": d.isoformat(), "actual": round(curr, 4),
                    "expected": row["yhat"],
                    "lo": row["lo"], "hi": row["hi"],
                })
        else:
            prev = _val(d - timedelta(days=7 if mode == "wow" else 1))
            if prev is None:
                no_data_days += 1
                continue
            evaluated += 1
            rate = ((curr - prev) / abs(prev)) if prev else None
            trig = (abs(rate) * 100 >= threshold) if rate is not None else curr != 0
            if trig:
                alerts.append({
                    "day": d.isoformat(), "actual": round(curr, 4),
                    "prev": round(prev, 4),
                    "change_rate_pct": (
                        round(rate * 100, 2) if rate is not None else None
                    ),
                })
    return {
        "metric": metric.name,
        "watch_mode": mode,
        "threshold_pct": threshold,
        "window": {"start": eval_start.isoformat(), "end": end.isoformat()},
        "days_evaluated": evaluated,
        "no_data_days": no_data_days,
        "alert_count": len(alerts),
        "alert_rate_pct": (
            round(len(alerts) / evaluated * 100, 2) if evaluated else None
        ),
        "alerts": alerts,
        "sql": series_sql,
    }


def run_subscription(
    sub: dict[str, Any],
    schema_store: SchemaStore | None = None,
    metric_store: MetricStore | None = None,
    today: date | None = None,
    push_fn: Callable[..., tuple[bool, str]] = push_card,
    favorites: FavoritesStore | None = None,
) -> dict[str, Any]:
    """Execute one subscription and push its card. Never raises: the outcome
    (including the pushed error card) is returned as a dict."""
    name = sub.get("name", sub.get("id", "?"))
    webhook = (sub.get("webhook_url") or "").strip()

    def _fail(error: str) -> dict[str, Any]:
        if webhook:
            push_fn(webhook, f"❌ {name}", f"订阅执行失败：\n{error}", ok=False)
        return {"status": "error", "error": error, "sql": ""}

    try:
        if schema_store is None:
            from .executor import schema_ddl_path_from_env

            ddl = Path(schema_ddl_path_from_env())
            if not ddl.is_file():
                return _fail(f"schema DDL 不存在: {ddl}")
            schema_store = SchemaStore.from_file(ddl)
        if metric_store is None:
            metric_store, _errors = load_metric_store(schema_store)

        if sub.get("source_type") in ("metric_watch", "freshness", "digest"):
            db_config = resolve_db_config(sub)
            if db_config is None:
                return _fail("无法解析数据库连接（检查连接预设名或环境变量配置）")
            runner = {
                "freshness": _run_freshness,
                "digest": _run_digest,
            }.get(sub.get("source_type", ""), _run_metric_watch)
            return runner(
                sub, schema_store, metric_store,
                create_executor(db_config), today or date.today(), push_fn,
            )

        sql = _build_subscription_sql(
            sub, schema_store, metric_store, today, favorites,
        )
        validation = validate_sql(sql, schema_store)
        if not validation.ok:
            return _fail("SQL rejected: " + "; ".join(validation.errors))
        ds_type = sub.get("ds_type", "hive")
        final_sql = enforce_limit(sql, dialect=ds_type)

        db_config = resolve_db_config(sub)
        if db_config is None:
            return _fail(
                "无法解析数据库连接（检查连接预设名或环境变量配置）"
            )
        result = create_executor(db_config).run(final_sql, max_rows=1000)
    except Exception as exc:
        from .tools import _sanitize_db_error

        return _fail(_sanitize_db_error(str(exc)))

    from .qlog import QueryLogger
    QueryLogger().log(
        user_query=f"[subscription] {name}", generated_sql=final_sql,
        status="success", matched_tables=validation.tables,
        exec_time_ms=result.elapsed_ms, row_count=result.row_count,
        extra={"source": "subscription", "metric": sub.get("metric", "")},
    )

    pushed, push_msg = True, ""
    if webhook:
        body = render_card_markdown(
            result.columns, [tuple(r) for r in result.rows], sql=final_sql,
        )
        # chart embedding: best-effort, needs FEISHU_APP_ID/SECRET for upload
        img_key = ""
        if detect_channel(webhook) == "feishu":
            png = _chart_png(result.columns, [tuple(r) for r in result.rows])
            if png:
                img_key = upload_feishu_image(png)
        pushed, push_msg = push_fn(
            webhook, f"📊 {name}", body, ok=True, img_key=img_key,
        )

    return {
        "status": "success" if pushed else "push_failed",
        "error": "" if pushed else push_msg,
        "sql": final_sql,
        "columns": result.columns,
        "rows": [list(r) for r in result.rows[:_CARD_MAX_ROWS]],
        "row_count": result.row_count,
    }


# ----------------------------------------------------------------------
# Scheduler
# ----------------------------------------------------------------------


#: catch-up cap default: after a stall (slow run_fn, host sleep) only this
#: many of the most recent missed minutes are replayed, so a long sleep
#: never triggers a burst of stale fires. Override per-Scheduler via the
#: ``catchup_minutes`` constructor arg or the ``SEATUNNEL_SUB_CATCHUP_MINUTES``
#: environment variable (clamped to 0..1440).
_MAX_CATCHUP_MINUTES = 10


def _catchup_minutes_from_env() -> int:
    raw = os.environ.get("SEATUNNEL_SUB_CATCHUP_MINUTES", "")
    try:
        value = int(raw)
    except ValueError:
        return _MAX_CATCHUP_MINUTES
    return max(0, min(1440, value))


class Scheduler:
    """Daemon-thread cron loop. One fire per subscription per matched minute.

    A slow ``run_fn`` can push the next tick past a whole minute; missed
    minutes (up to ``catchup_minutes``) are replayed on the next check
    so same-minute crons of other subscriptions are not silently dropped."""

    def __init__(
        self,
        store: SubscriptionStore | None = None,
        tick_seconds: int = 20,
        run_fn: Callable[[dict[str, Any]], dict[str, Any]] = run_subscription,
        catchup_minutes: int | None = None,
    ) -> None:
        self.store = store or SubscriptionStore()
        self.tick_seconds = tick_seconds
        self.run_fn = run_fn
        self.catchup_minutes = (
            max(0, min(1440, catchup_minutes))
            if catchup_minutes is not None
            else _catchup_minutes_from_env()
        )
        self._fired: dict[str, str] = {}  # sub_id -> "YYYY-mm-dd HH:MM" last fired
        self._last_minute: datetime | None = None  # last minute already checked
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def check_once(self, now: datetime | None = None) -> list[str]:
        """Run every due subscription once; returns the ids that fired."""
        now = now or datetime.now()
        current = now.replace(second=0, microsecond=0)
        minutes: list[datetime] = []
        if self._last_minute is not None and self._last_minute < current:
            m = self._last_minute + timedelta(minutes=1)
            while m < current:
                minutes.append(m)
                m += timedelta(minutes=1)
            cap = self.catchup_minutes
            minutes = minutes[-cap:] if cap > 0 else []
        minutes.append(current)
        if self._last_minute is None or current > self._last_minute:
            self._last_minute = current

        fired: list[str] = []
        subs = self.store.list()
        for minute in minutes:
            minute_key = minute.strftime("%Y-%m-%d %H:%M")
            for sub in subs:
                if not sub.get("enabled", True):
                    continue
                sub_id = sub.get("id", "")
                try:
                    spec = parse_cron(sub.get("cron", ""))
                except ValueError:
                    continue
                if not spec.matches(minute) or self._fired.get(sub_id) == minute_key:
                    continue
                self._fired[sub_id] = minute_key
                fired.append(sub_id)
                try:
                    outcome = self.run_fn(sub)
                    self.store.record_run(
                        sub_id, outcome.get("status", "error"),
                        outcome.get("error", ""),
                    )
                    if "alert_state" in outcome:
                        self.store.record_alert_state(
                            sub_id, outcome["alert_state"],
                        )
                except Exception as exc:  # run_fn contract says it never raises, but
                    logger.exception("Subscription %s failed", sub_id)
                    self.store.record_run(sub_id, "error", str(exc))
        return fired

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        def _loop() -> None:
            while not self._stop.wait(self.tick_seconds):
                try:
                    self.check_once()
                except Exception:
                    logger.exception("Scheduler tick failed")

        self._stop.clear()
        self._thread = threading.Thread(
            target=_loop, name="t2s-subscriptions", daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()


_global_scheduler: Scheduler | None = None
_global_lock = threading.Lock()


def start_global_scheduler() -> Scheduler:
    """Idempotent process-wide scheduler used by the web UI."""
    global _global_scheduler
    with _global_lock:
        if _global_scheduler is None:
            _global_scheduler = Scheduler()
            _global_scheduler.start()
        return _global_scheduler
