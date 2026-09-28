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

import json
import logging
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .executor import DatabaseConfig, config_from_env, create_executor
from .favorites import FavoritesStore, apply_params
from .metrics import MetricError, MetricStore, build_metric_sql, load_metric_store
from .partition import TimeRange, pt_value
from .schema import SchemaStore
from .validator import enforce_limit, validate_sql

logger = logging.getLogger(__name__)

_MAX_SUBSCRIPTIONS = 100
_CARD_MAX_ROWS = 10

SOURCE_TYPES = ("metric", "favorite")


# ----------------------------------------------------------------------
# Cron (standard 5 fields, zero-dep)
# ----------------------------------------------------------------------

_FIELD_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
_FIELD_NAMES = ("minute", "hour", "day-of-month", "month", "day-of-week")


def _parse_field(expr: str, lo: int, hi: int, name: str) -> frozenset[int]:
    values: set[int] = set()
    for part in expr.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            try:
                step = int(step_s)
            except ValueError:
                raise ValueError(f"cron {name}: 无效步长 '{step_s}'")
            if step < 1:
                raise ValueError(f"cron {name}: 步长必须 >= 1")
        if part in ("*", ""):
            start, end = lo, hi
        elif "-" in part:
            a, b = part.split("-", 1)
            try:
                start, end = int(a), int(b)
            except ValueError:
                raise ValueError(f"cron {name}: 无效范围 '{part}'")
        else:
            try:
                start = end = int(part)
            except ValueError:
                raise ValueError(f"cron {name}: 无效值 '{part}'")
        if not (lo <= start <= hi and lo <= end <= hi and start <= end):
            raise ValueError(f"cron {name}: 取值需在 {lo}-{hi} 内")
        values.update(range(start, end + 1, step))
    return frozenset(values)


@dataclass(frozen=True)
class CronSpec:
    minute: frozenset[int]
    hour: frozenset[int]
    dom: frozenset[int]
    month: frozenset[int]
    dow: frozenset[int]  # 0 = Monday (Python convention), 6 = Sunday

    def matches(self, dt: datetime) -> bool:
        return (
            dt.minute in self.minute
            and dt.hour in self.hour
            and dt.day in self.dom
            and dt.month in self.month
            and dt.weekday() in self.dow
        )


def parse_cron(expr: str) -> CronSpec:
    """Parse ``M H DoM Mon DoW``. Day-of-week: 0=Monday .. 6=Sunday
    (7 is accepted as Sunday for cron habit)."""
    fields = (expr or "").split()
    if len(fields) != 5:
        raise ValueError("cron 表达式必须是 5 个字段: 分 时 日 月 周")
    parsed = []
    for raw, (lo, hi), name in zip(fields, _FIELD_RANGES, _FIELD_NAMES):
        if name == "day-of-week":
            raw = raw.replace("7", "6") if raw.strip() == "7" else raw
        parsed.append(_parse_field(raw, lo, hi, name))
    return CronSpec(*parsed)


# ----------------------------------------------------------------------
# Built-in date macros for favorite params
# ----------------------------------------------------------------------


def builtin_params(today: date | None = None) -> dict[str, str]:
    """Date macros usable as ``${name}`` in favorite SQL / extra filters."""
    today = today or date.today()
    yesterday = today - timedelta(days=1)
    month_start = today.replace(day=1)
    return {
        "today": today.isoformat(),
        "yesterday": yesterday.isoformat(),
        "today_pt": pt_value(today),
        "yesterday_pt": pt_value(yesterday),
        "month_start": month_start.isoformat(),
        "month_start_pt": pt_value(month_start),
    }


# ----------------------------------------------------------------------
# Store (same atomic-JSON pattern as favorites)
# ----------------------------------------------------------------------


class SubscriptionStore:
    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:  # env read at init time so tests can redirect it
            path = os.getenv("T2S_SUBSCRIPTIONS_PATH", "config/t2s_subscriptions.json")
        self.path = Path(path)
        self._lock = threading.Lock()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _write(self, data: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(data, ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, str(self.path))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

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
        if source_type == "metric" and not metric.strip():
            raise ValueError("metric 订阅必须给出指标名")
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
        with self._lock:
            data = self._read()
            data.append(entry)
            if len(data) > _MAX_SUBSCRIPTIONS:
                data = data[-_MAX_SUBSCRIPTIONS:]
            self._write(data)
        return entry

    def delete(self, sub_id: str) -> bool:
        with self._lock:
            data = self._read()
            before = len(data)
            data = [e for e in data if e.get("id") != sub_id]
            if len(data) < before:
                self._write(data)
                return True
            return False

    def set_enabled(self, sub_id: str, enabled: bool) -> bool:
        with self._lock:
            data = self._read()
            for entry in data:
                if entry.get("id") == sub_id:
                    entry["enabled"] = bool(enabled)
                    self._write(data)
                    return True
            return False

    def record_run(self, sub_id: str, status: str, error: str = "") -> None:
        with self._lock:
            data = self._read()
            for entry in data:
                if entry.get("id") == sub_id:
                    entry["last_run_at"] = datetime.now(timezone.utc).isoformat(
                        timespec="seconds"
                    )
                    entry["last_status"] = status
                    entry["last_error"] = error[:500]
                    self._write(data)
                    return


# ----------------------------------------------------------------------
# Feishu push (stdlib only)
# ----------------------------------------------------------------------


def render_card_markdown(
    columns: list[str], rows: list[tuple], max_rows: int = _CARD_MAX_ROWS,
) -> str:
    """Feishu lark_md table (pipe-drawn; lark_md has no real tables)."""
    lines = [" | ".join(str(c) for c in columns)]
    for row in rows[:max_rows]:
        lines.append(" | ".join("" if v is None else str(v) for v in row))
    if len(rows) > max_rows:
        lines.append(f"... 共 {len(rows)} 行，仅展示前 {max_rows} 行")
    return "\n".join(lines)


def push_feishu(
    webhook_url: str,
    title: str,
    body_markdown: str,
    ok: bool = True,
    timeout: int = 15,
) -> tuple[bool, str]:
    """POST an interactive card to a Feishu incoming webhook."""
    import urllib.request

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue" if ok else "red",
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": body_markdown}},
            ],
        },
    }
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(card, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # network / HTTP errors
        return False, str(exc)
    # Feishu returns {"code": 0} (new) or {"StatusCode": 0} (legacy) on success.
    code = payload.get("code", payload.get("StatusCode", -1))
    if code == 0:
        return True, "ok"
    return False, payload.get("msg", str(payload))


# ----------------------------------------------------------------------
# Running a subscription
# ----------------------------------------------------------------------


def resolve_db_config(sub: dict[str, Any]) -> DatabaseConfig | None:
    """Resolve the connection server-side: preset name > sqlite path > env."""
    ds_type = sub.get("ds_type", "hive")
    preset_name = (sub.get("connection") or "").strip()
    if preset_name:
        from ..data_comparison.presets import PresetsStore

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


def run_subscription(
    sub: dict[str, Any],
    schema_store: SchemaStore | None = None,
    metric_store: MetricStore | None = None,
    today: date | None = None,
    push_fn: Callable[..., tuple[bool, str]] = push_feishu,
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
        body = render_card_markdown(result.columns, [tuple(r) for r in result.rows])
        pushed, push_msg = push_fn(webhook, f"📊 {name}", body, ok=True)

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


class Scheduler:
    """Daemon-thread cron loop. One fire per subscription per matched minute."""

    def __init__(
        self,
        store: SubscriptionStore | None = None,
        tick_seconds: int = 20,
        run_fn: Callable[[dict[str, Any]], dict[str, Any]] = run_subscription,
    ) -> None:
        self.store = store or SubscriptionStore()
        self.tick_seconds = tick_seconds
        self.run_fn = run_fn
        self._fired: dict[str, str] = {}  # sub_id -> "YYYY-mm-dd HH:MM" last fired
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def check_once(self, now: datetime | None = None) -> list[str]:
        """Run every due subscription once; returns the ids that fired."""
        now = now or datetime.now()
        minute_key = now.strftime("%Y-%m-%d %H:%M")
        fired: list[str] = []
        for sub in self.store.list():
            if not sub.get("enabled", True):
                continue
            sub_id = sub.get("id", "")
            try:
                spec = parse_cron(sub.get("cron", ""))
            except ValueError:
                continue
            if not spec.matches(now) or self._fired.get(sub_id) == minute_key:
                continue
            self._fired[sub_id] = minute_key
            fired.append(sub_id)
            try:
                outcome = self.run_fn(sub)
                self.store.record_run(
                    sub_id, outcome.get("status", "error"),
                    outcome.get("error", ""),
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
