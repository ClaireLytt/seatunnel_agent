# -*- coding: utf-8 -*-
"""Webhook notifications — one send() for DingTalk / Feishu / Slack / generic.

The observability features (cost anomalies, eval regressions, flaky CI) can
*detect*; this module makes them *tell someone*.  Configuration is two env
vars — ``NOTIFY_WEBHOOK_URL`` and optionally ``NOTIFY_KIND`` (auto-detected
from the URL otherwise) — so a cron line like::

    seatunnel-agent llmeval suite.yaml --fail-on regression --notify

alerts a group chat the moment a regression lands.  Transport is injectable
and failures never raise: an alert about a problem must not become one.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

KINDS = ("dingtalk", "feishu", "slack", "generic")


def detect_kind(url: str) -> str:
    u = (url or "").lower()
    if "dingtalk" in u:
        return "dingtalk"
    if "feishu" in u or "larksuite" in u:
        return "feishu"
    if "slack" in u:
        return "slack"
    return "generic"


def build_payload(kind: str, title: str, text: str) -> dict[str, Any]:
    """Platform-specific message body; *text* is markdown-ish plain text."""
    if kind == "dingtalk":
        return {"msgtype": "markdown",
                "markdown": {"title": title, "text": f"### {title}\n{text}"}}
    if kind == "feishu":
        return {"msg_type": "text",
                "content": {"text": f"{title}\n{text}"}}
    if kind == "slack":
        return {"text": f"*{title}*\n{text}"}
    return {"title": title, "text": text}


def _default_transport(url: str, body: bytes) -> None:
    from urllib.request import Request, urlopen
    req = Request(url, data=body,
                  headers={"Content-Type": "application/json",
                           "User-Agent": "seatunnel-agent"})
    with urlopen(req, timeout=15):  # noqa: S310 — user-configured webhook
        pass


def send(title: str, text: str,
         kind: str | None = None, url: str | None = None,
         transport: Callable[[str, bytes], None] | None = None) -> bool:
    """POST the alert; True on success, False (never raises) otherwise."""
    url = url or os.getenv("NOTIFY_WEBHOOK_URL", "")
    if not url:
        return False
    kind = (kind or os.getenv("NOTIFY_KIND") or detect_kind(url)).lower()
    if kind not in KINDS:
        kind = "generic"
    payload = build_payload(kind, title, text)
    try:
        (transport or _default_transport)(
            url, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        return True
    except Exception:  # noqa: BLE001 — alerting is best-effort
        return False
