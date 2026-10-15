# -*- coding: utf-8 -*-
"""Webhook notification for skew patrols (same JSON-POST convention as the
Data Comparison page's webhook: a generic ``{"text": ..., ...}`` payload
that DingTalk/WeCom/Slack-style incoming webhooks all accept)."""

from __future__ import annotations

import json

_WEBHOOK_TIMEOUT = 10.0


def post_webhook(url: str, payload: dict) -> tuple[bool, str]:
    """POST *payload* as JSON to *url*. Returns (success, status/message);
    never raises — a failed notification must not fail the patrol."""
    import urllib.error
    import urllib.request

    data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_WEBHOOK_TIMEOUT) as resp:  # noqa: S310
            return True, str(resp.status)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        return False, str(exc)
