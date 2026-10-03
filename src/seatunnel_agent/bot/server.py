# -*- coding: utf-8 -*-
"""GitHub webhook server — PR opened/updated → bot review comment.

Security: when a webhook secret is configured every delivery must carry a
valid ``X-Hub-Signature-256`` (HMAC-SHA256 of the raw body); anything else
is 401.  Network I/O (fetching the PR diff, posting the comment) goes
through injectable callables so the whole flow is testable offline; the
defaults use the GitHub REST API with ``GITHUB_TOKEN``.

Run it: ``seatunnel-agent bot --port 9000`` (secret via ``WEBHOOK_SECRET``).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request

from .core import BOT_MARKER, review_patch

_HANDLED_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review"}


def _gh_request(url: str, data: bytes | None = None,
                accept: str = "application/vnd.github+json") -> bytes:
    from urllib.request import Request as UrlRequest
    from urllib.request import urlopen
    headers = {"Accept": accept, "User-Agent": "seatunnel-agent-bot"}
    token = os.getenv("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = UrlRequest(url, data=data, headers=headers)
    with urlopen(req, timeout=30) as resp:  # noqa: S310 — api.github.com
        return resp.read()


def default_fetch_diff(payload: dict[str, Any]) -> str:
    """The PR's unified diff via the pulls API (works for private repos)."""
    url = payload["pull_request"]["url"]
    return _gh_request(url, accept="application/vnd.github.v3.diff").decode(
        "utf-8", errors="replace")


def default_post_comment(payload: dict[str, Any], body: str) -> None:
    url = payload["pull_request"]["comments_url"]  # issues comments API
    _gh_request(url, data=json.dumps({"body": body}).encode("utf-8"))


def default_find_bot_comment(payload: dict[str, Any]) -> str | None:
    """URL of the existing bot comment (by BOT_MARKER), or None."""
    url = payload["pull_request"]["comments_url"] + "?per_page=100"
    comments = json.loads(_gh_request(url))
    for c in comments:
        if BOT_MARKER in (c.get("body") or ""):
            return str(c.get("url") or "") or None
    return None


def default_update_comment(comment_url: str, body: str) -> None:
    from urllib.request import Request as UrlRequest
    from urllib.request import urlopen
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "seatunnel-agent-bot",
               "Content-Type": "application/json"}
    token = os.getenv("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = UrlRequest(comment_url,
                     data=json.dumps({"body": body}).encode("utf-8"),
                     headers=headers, method="PATCH")
    with urlopen(req, timeout=30):  # noqa: S310 — api.github.com
        pass


RESOLVED_BODY = (f"{BOT_MARKER}\n## 🤖 SeaTunnel Agent Bot\n\n"
                 "✅ 此前报告的问题在最新改动中已不再出现。")


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, f"sha256={digest}")


def create_bot_app(secret: str = "",
                   fetch_diff: Callable[[dict], str] | None = None,
                   post_comment: Callable[[dict, str], None] | None = None,
                   find_bot_comment: Callable[[dict], str | None] | None = None,
                   update_comment: Callable[[str, str], None] | None = None,
                   ) -> FastAPI:
    fetch_diff = fetch_diff or default_fetch_diff
    post_comment = post_comment or default_post_comment
    find_bot_comment = find_bot_comment or default_find_bot_comment
    update_comment = update_comment or default_update_comment
    app = FastAPI(title="seatunnel-agent bot")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "agent": "bot"}

    @app.post("/webhook")
    async def webhook(request: Request) -> dict[str, Any]:
        body = await request.body()
        if secret and not verify_signature(
                secret, body, request.headers.get("X-Hub-Signature-256")):
            raise HTTPException(status_code=401, detail="bad signature")
        event = request.headers.get("X-GitHub-Event", "")
        if event == "ping":
            return {"status": "pong"}
        if event != "pull_request":
            return {"status": "ignored", "event": event}
        try:
            payload = json.loads(body)
        except ValueError:
            raise HTTPException(status_code=400, detail="bad JSON")
        action = payload.get("action", "")
        if action not in _HANDLED_ACTIONS:
            return {"status": "ignored", "action": action}
        try:
            patch = fetch_diff(payload)
        except Exception as exc:  # noqa: BLE001 — network/auth problems
            raise HTTPException(status_code=502,
                                detail=f"diff fetch failed: {exc}")
        findings, comment = review_patch(patch)
        # dedupe: one bot comment per PR, updated in place on every push —
        # a bot that stacks near-identical comments gets muted within a week
        try:
            existing = find_bot_comment(payload)
        except Exception:  # noqa: BLE001 — listing failed: fall back to post
            existing = None
        commented = False
        try:
            if comment:
                if existing:
                    update_comment(existing, comment)
                else:
                    post_comment(payload, comment)
                commented = True
            elif existing:
                # findings resolved by this push: say so instead of leaving
                # a stale warning standing
                update_comment(existing, RESOLVED_BODY)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502,
                                detail=f"comment post failed: {exc}")
        return {"status": "reviewed", "findings": len(findings),
                "commented": commented, "updated": bool(existing),
                "marker": BOT_MARKER}

    return app
