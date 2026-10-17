"""Capture light/dark screenshots of the sql_review page (before/after)."""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import expect, sync_playwright

from seatunnel_agent.agents.data.sql_review import rlog
from seatunnel_agent.agents.data.sql_review.api import router

tag = sys.argv[1]  # "before" | "after"
outdir = Path("docs/reports/shots")
outdir.mkdir(parents=True, exist_ok=True)

rlog.ReviewLogger.log = lambda self, **kw: None  # type: ignore[method-assign]

app = FastAPI()
app.include_router(router)
app.mount("/sqlreview", StaticFiles(directory="frontend/sql_review/dist", html=True))

with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
threading.Thread(target=server.run, daemon=True).start()
while not server.started:
    time.sleep(0.1)
url = f"http://127.0.0.1:{port}/sqlreview/"

FAKE_STATS = {
    "summary": {
        "reviews": 12,
        "findings": 31,
        "severities": {"critical": 6, "risk": 14, "suggestion": 11},
        "top_categories": [
            {"category": "select_star", "label": "SELECT *", "count": 9},
            {"category": "null_compare", "label": "= NULL", "count": 7},
        ],
    },
    "daily": [
        {"day": f"10-{d:02d}", "critical": d % 3, "risk": (d * 2) % 5, "suggestion": (d + 1) % 4}
        for d in range(6, 18)
    ],
}

with sync_playwright() as p:
    browser = p.chromium.launch()
    for scheme in ("light", "dark"):
        ctx = browser.new_context(color_scheme=scheme, viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.route(
            "**/api/sql_review/stats",
            lambda route: route.fulfill(
                content_type="application/json", body=json.dumps(FAKE_STATS)
            ),
        )
        page.goto(url, wait_until="networkidle")
        page.locator("#sql").fill("SELECT * FROM ods.user_log WHERE a = NULL")
        page.get_by_role("button", name="Start Review").click()
        expect(page.locator(".sr-report")).to_be_visible(timeout=15000)
        page.get_by_role("button", name="Review History Stats").click()
        page.wait_for_selector(".recharts-bar", timeout=10000)
        time.sleep(1)
        page.screenshot(path=str(outdir / f"sqlreview-align-{tag}-{scheme}.png"), full_page=True)
        ctx.close()
    browser.close()
server.should_exit = True
print("done", tag)
