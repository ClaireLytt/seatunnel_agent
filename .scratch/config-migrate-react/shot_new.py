"""Screenshot the React /migrate page (en + zh) via in-process uvicorn."""
import socket
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from seatunnel_agent.agents.data.config_migrate.api import router
from seatunnel_agent.agents.data.config_migrate.manifest import MANIFEST
from seatunnel_agent.hub.registry import frontend_dist

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / frontend_dist(MANIFEST)
OUT = ROOT / ".scratch" / "config-migrate-react" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.include_router(router)
app.mount("/migrate", StaticFiles(directory=DIST, html=True))

with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]

server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                       log_level="warning"))
t = threading.Thread(target=server.run, daemon=True)
t.start()
deadline = time.time() + 15
while not server.started:
    if time.time() > deadline:
        raise SystemExit("uvicorn did not start")
    time.sleep(0.1)

url = f"http://127.0.0.1:{port}/migrate/"
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(url, wait_until="networkidle")
    page.screenshot(path=str(OUT / "new_en.png"), full_page=True)
    print("saved new_en.png")

    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_cookies([{"name": "st-lang", "value": "zh-CN",
                      "domain": "127.0.0.1", "path": "/"}])
    zh = ctx.new_page()
    zh.goto(url, wait_until="networkidle")
    zh.screenshot(path=str(OUT / "new_zh.png"), full_page=True)
    print("saved new_zh.png")
    browser.close()

server.should_exit = True
t.join(timeout=5)
print("done")
