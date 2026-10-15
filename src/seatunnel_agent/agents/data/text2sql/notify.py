"""Notification channels for subscription pushes (Feishu / DingTalk /
WeCom / email), stdlib only.

Moved verbatim out of subscriptions.py, which re-exports the public names.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable

_CARD_MAX_ROWS = 10


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
    except Exception:
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


