"""Capture light/dark (en/zh) full-page screenshots of /datacompare.

Serves the built dist + API in-process (test_datacompare_page.py harness),
connects both sides to SQLite fixtures, opens every accordion, runs a
schema compare so the results panel shows a server card, then shoots
light/dark x en/zh (theme via browser color_scheme -> prefers-color-scheme,
language via the st-lang cookie, sqlreview shoot.py precedent).
"""
from __future__ import annotations

import socket
import sqlite3
import sys
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import expect, sync_playwright

from seatunnel_agent.agents.data.data_comparison.api import router

ROOT = Path(__file__).resolve().parents[2]
outdir = ROOT / "docs" / "reports" / "shots"
outdir.mkdir(parents=True, exist_ok=True)
tmp = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".scratch" / "dc-shoot-tmp"
tmp.mkdir(parents=True, exist_ok=True)


def make_db(path: Path, extra_col: bool) -> str:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    cols = "id INTEGER, val TEXT" + (", extra REAL" if extra_col else "")
    conn.execute(f"CREATE TABLE orders ({cols})")
    conn.executemany("INSERT INTO orders (id, val) VALUES (?, ?)",
                     [(1, "x"), (2, "y")])
    conn.commit()
    conn.close()
    return str(path)


db_a = make_db(tmp / "a.db", extra_col=False)
db_b = make_db(tmp / "b.db", extra_col=True)

app = FastAPI()
app.include_router(router)
app.mount("/datacompare",
          StaticFiles(directory=ROOT / "frontend" / "datacompare" / "dist", html=True))

with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                       log_level="warning"))
threading.Thread(target=server.run, daemon=True).start()
while not server.started:
    time.sleep(0.1)
url = f"http://127.0.0.1:{port}/datacompare/"

with sync_playwright() as p:
    browser = p.chromium.launch()
    for scheme in ("light", "dark"):
        for lang in ("en", "zh"):
            ctx = browser.new_context(color_scheme=scheme,
                                      viewport={"width": 1440, "height": 1000})
            ctx.add_cookies([{"name": "st-lang", "value": lang,
                              "url": f"http://127.0.0.1:{port}"}])
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle")

            # connect both sides to the SQLite fixtures, pick the table
            for side, db in (("a", db_a), ("b", db_b)):
                page.locator(f"#ds-{side}").select_option("sqlite")
                page.locator(f"#db-{side}").fill(db)
                box = page.get_by_test_id(f"connect-{side}")
                box.get_by_role("button").first.click()
                expect(page.get_by_test_id(f"status-{side}")).to_contain_text("✅")
                page.locator(f"#table-{side}").select_option("orders")

            # open every accordion so dark tokens show on all sections
            for tid in ("presets-card", "accordion-incremental", "accordion-quality",
                        "accordion-skew", "accordion-checksum", "accordion-partition",
                        "accordion-custom-agg", "accordion-sql", "sync-card",
                        "lineage-card", "env-card", "reports-card", "templates-card",
                        "schedule-card", "trends-card"):
                page.get_by_test_id(tid).locator("button").first.click()

            # render a server card into the results panel
            page.get_by_test_id("action-schema").click()
            expect(page.get_by_test_id("result-cards")).to_be_visible(timeout=15000)
            time.sleep(0.8)

            suffix = "-zh" if lang == "zh" else ""
            page.screenshot(
                path=str(outdir / f"datacompare-react-{scheme}{suffix}-full.png"),
                full_page=True)
            ctx.close()
    browser.close()
server.should_exit = True
print("done")
