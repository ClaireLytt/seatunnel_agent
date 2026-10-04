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
from .attribution import NULL_LABEL
from .favorites import FavoritesStore, apply_params
from .metrics import MetricError, MetricStore, build_metric_sql, load_metric_store
from .partition import TimeRange, pt_value
from .schema import SchemaStore
from .validator import enforce_limit, validate_sql

logger = logging.getLogger(__name__)

_MAX_SUBSCRIPTIONS = 100
_CARD_MAX_ROWS = 10

SOURCE_TYPES = ("metric", "favorite", "metric_watch")

#: metric_watch comparison modes: dod = 昨天 vs 前天, wow = 昨天 vs 上周同日
WATCH_MODES = ("dod", "wow")


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
        threshold_pct: float = 10.0,
        watch_mode: str = "dod",
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
        if source_type in ("metric", "metric_watch") and not metric.strip():
            raise ValueError(f"{source_type} 订阅必须给出指标名")
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
    from .masking import apply_masking

    rows, _masked = apply_masking(columns, list(rows))
    lines = [" | ".join(str(c) for c in columns)]
    for row in rows[:max_rows]:
        lines.append(" | ".join("" if v is None else str(v) for v in row))
    if len(rows) > max_rows:
        lines.append(f"... 共 {len(rows)} 行，仅展示前 {max_rows} 行")
    return "\n".join(lines)


def _feishu_tenant_token(timeout: int = 15) -> str:
    """App tenant token from FEISHU_APP_ID/FEISHU_APP_SECRET ('' if unset)."""
    import urllib.request

    app_id = os.getenv("FEISHU_APP_ID", "").strip()
    app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        return ""
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("tenant_access_token", "") if data.get("code") == 0 else ""


def upload_feishu_image(png_bytes: bytes, timeout: int = 30) -> str:
    """Upload a PNG via the Feishu image API; returns img_key ('' on any
    failure — chart embedding is strictly best-effort and needs app creds)."""
    import urllib.request
    import uuid as _uuid

    try:
        token = _feishu_tenant_token(timeout)
        if not token:
            return ""
        boundary = f"----st{_uuid.uuid4().hex}"
        body = b"".join([
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="image_type"\r\n\r\nmessage\r\n',
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="image"; filename="chart.png"\r\n',
            b"Content-Type: image/png\r\n\r\n",
            png_bytes,
            f"\r\n--{boundary}--\r\n".encode(),
        ])
        req = urllib.request.Request(
            "https://open.feishu.cn/open-apis/im/v1/images",
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") == 0:
            return data.get("data", {}).get("image_key", "")
    except Exception:  # noqa: BLE001 — best-effort by contract
        pass
    return ""


def _chart_png(columns: list[str], rows: list[tuple]) -> bytes:
    """Auto-detected chart PNG for the result ('' bytes when not chartable
    or matplotlib is missing)."""
    try:
        import io

        from .chart import build_chart, detect_chart_type

        ct = detect_chart_type(columns, rows)
        if not ct:
            return b""
        fig = build_chart(columns, rows, ct)
        if fig is None:
            return b""
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
        import matplotlib.pyplot as plt

        plt.close(fig)
        return buf.getvalue()
    except Exception:
        return b""


def push_feishu(
    webhook_url: str,
    title: str,
    body_markdown: str,
    ok: bool = True,
    timeout: int = 15,
    img_key: str = "",
) -> tuple[bool, str]:
    """POST an interactive card to a Feishu incoming webhook."""
    import urllib.request

    elements: list[dict] = [
        {"tag": "div", "text": {"tag": "lark_md", "content": body_markdown}},
    ]
    if img_key:
        elements.append({
            "tag": "img", "img_key": img_key,
            "alt": {"tag": "plain_text", "content": "chart"},
        })
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue" if ok else "red",
            },
            "elements": elements,
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
# Other channels: DingTalk / WeCom bots, email — dispatched by target URL
# ----------------------------------------------------------------------


def _post_json(url: str, payload: dict, timeout: int) -> tuple[bool, dict | str]:
    """POST JSON; returns (transport_ok, parsed_response | error_str)."""
    import urllib.request

    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # network / HTTP errors
        return False, str(exc)


def push_dingtalk(
    webhook_url: str,
    title: str,
    body_markdown: str,
    ok: bool = True,
    timeout: int = 15,
    img_key: str = "",  # signature-compatible; DingTalk has no img upload here
) -> tuple[bool, str]:
    """POST a markdown message to a DingTalk custom-robot webhook."""
    del img_key
    icon = "" if ok else "❌ "
    sent, payload = _post_json(webhook_url, {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": f"## {icon}{title}\n\n{body_markdown}",
        },
    }, timeout)
    if not sent:
        return False, str(payload)
    if isinstance(payload, dict) and payload.get("errcode", -1) == 0:
        return True, "ok"
    return False, payload.get("errmsg", str(payload)) if isinstance(payload, dict) else str(payload)


def push_wecom(
    webhook_url: str,
    title: str,
    body_markdown: str,
    ok: bool = True,
    timeout: int = 15,
    img_key: str = "",  # signature-compatible; not applicable
) -> tuple[bool, str]:
    """POST a markdown message to a WeCom (企业微信) group-bot webhook."""
    del img_key
    icon = "" if ok else "❌ "
    content = f"## {icon}{title}\n\n{body_markdown}"
    # WeCom caps markdown content at 4096 bytes (UTF-8).
    while len(content.encode("utf-8")) > 4000:
        content = content[: int(len(content) * 0.9)]
    sent, payload = _post_json(webhook_url, {
        "msgtype": "markdown",
        "markdown": {"content": content},
    }, timeout)
    if not sent:
        return False, str(payload)
    if isinstance(payload, dict) and payload.get("errcode", -1) == 0:
        return True, "ok"
    return False, payload.get("errmsg", str(payload)) if isinstance(payload, dict) else str(payload)


def push_email(
    target: str,
    title: str,
    body_markdown: str,
    ok: bool = True,
    timeout: int = 15,
    img_key: str = "",  # signature-compatible; not applicable
) -> tuple[bool, str]:
    """Send the card body as a plain-text email. Target is ``mailto:addr``;
    SMTP settings come from SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS
    (STARTTLS by default, SMTP_TLS=0 to disable)."""
    del img_key
    import smtplib
    from email.mime.text import MIMEText

    addr = target[len("mailto:"):].strip() if target.startswith("mailto:") else target.strip()
    host = os.getenv("SMTP_HOST", "").strip()
    if not host or not addr:
        return False, "SMTP_HOST 未配置或收件地址为空"
    # The address and title come from the user-editable subscription file —
    # reject/strip anything that could smuggle extra SMTP headers.
    if any(c in addr for c in " \t\r\n,;"):
        return False, f"收件地址非法: {addr!r}"
    title = title.replace("\r", " ").replace("\n", " ")
    port = int(os.getenv("SMTP_PORT", "587") or 587)
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASS", "")
    sender = os.getenv("SMTP_FROM", user or "seatunnel-agent@localhost").strip()

    msg = MIMEText(body_markdown, "plain", "utf-8")
    msg["Subject"] = ("" if ok else "[FAILED] ") + title
    msg["From"] = sender
    msg["To"] = addr
    try:
        with smtplib.SMTP(host, port, timeout=timeout) as smtp:
            if os.getenv("SMTP_TLS", "1").strip() != "0":
                smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.sendmail(sender, [addr], msg.as_string())
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def detect_channel(target: str) -> str:
    """Push channel from the target URL: feishu / dingtalk / wecom / email."""
    t = (target or "").strip().lower()
    if t.startswith("mailto:") or ("@" in t and "://" not in t):
        return "email"
    if "oapi.dingtalk.com" in t:
        return "dingtalk"
    if "qyapi.weixin.qq.com" in t:
        return "wecom"
    return "feishu"  # open.feishu.cn / larksuite, and the historic default


_CHANNEL_PUSHERS: dict[str, Callable[..., tuple[bool, str]]] = {
    "feishu": push_feishu,
    "dingtalk": push_dingtalk,
    "wecom": push_wecom,
    "email": push_email,
}


def push_card(
    webhook_url: str,
    title: str,
    body_markdown: str,
    ok: bool = True,
    timeout: int = 15,
    img_key: str = "",
) -> tuple[bool, str]:
    """Channel-dispatching push: the subscription schema stays a single
    target URL, and the channel is inferred from its domain (feishu is the
    default, preserving pre-multi-channel behavior)."""
    pusher = _CHANNEL_PUSHERS[detect_channel(webhook_url)]
    return pusher(webhook_url, title, body_markdown, ok=ok, timeout=timeout,
                  img_key=img_key)


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
    ref = yesterday - timedelta(days=7 if sub.get("watch_mode") == "wow" else 1)
    ds_type = sub.get("ds_type", "hive")

    def _total(day: date) -> float | None:
        sql = build_metric_sql(
            metric, metric_store, schema_store,
            time_range=TimeRange(start=day, end=day),
        )
        validation = validate_sql(sql, schema_store)
        if not validation.ok:
            raise MetricError("SQL rejected: " + "; ".join(validation.errors))
        result = executor.run(enforce_limit(sql, dialect=ds_type), max_rows=10)
        if not result.rows or result.rows[0][-1] is None:
            # additive: no rows means 0; a NULL ratio (denominator 0 or no
            # data) is UNDEFINED, not 0 — coercing it would fire a false
            # "-100%" alert
            return None if metric.is_ratio else 0.0
        return float(result.rows[0][-1])

    curr, prev = _total(yesterday), _total(ref)
    if curr is None or prev is None:
        return {
            "status": "no_data", "error": "", "sql": "",
            "curr": curr, "prev": prev, "delta": None,
            "change_rate_pct": None,
            "threshold_pct": float(sub.get("threshold_pct", 10.0)),
            "curr_day": yesterday.isoformat(), "ref_day": ref.isoformat(),
            "note": "比率在该日无定义（分母为 0 或无数据），跳过告警",
        }
    delta = curr - prev
    rate = (delta / abs(prev)) if prev else None
    threshold = float(sub.get("threshold_pct", 10.0))
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
    if not triggered:
        return outcome  # silence by design — no card below the threshold

    # top contributors on the first allowed dimension (best-effort).
    # Ratio metrics have no dimensions of their own: fall back to the
    # numerator∩denominator intersection build_metric_sql would accept.
    allowed_dims = list(metric.dimensions)
    if metric.is_ratio and not allowed_dims:
        num = metric_store.get(metric.numerator)
        den = metric_store.get(metric.denominator)
        if num is not None and den is not None:
            den_set = {d.lower() for d in den.dimensions}
            allowed_dims = [d for d in num.dimensions if d.lower() in den_set]
    top_lines = ""
    dim = (sub.get("dimensions") or allowed_dims[:1] or [None])[0]
    if dim:
        try:
            def _by_dim(day: date) -> dict[str, float]:
                sql = build_metric_sql(
                    metric, metric_store, schema_store, dimensions=[dim],
                    time_range=TimeRange(start=day, end=day),
                )
                result = executor.run(
                    enforce_limit(sql, dialect=ds_type), max_rows=1000)
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

        if sub.get("source_type") == "metric_watch":
            db_config = resolve_db_config(sub)
            if db_config is None:
                return _fail("无法解析数据库连接（检查连接预设名或环境变量配置）")
            return _run_metric_watch(
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
        body = render_card_markdown(result.columns, [tuple(r) for r in result.rows])
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
