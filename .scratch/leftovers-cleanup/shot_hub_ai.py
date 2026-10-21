"""Screenshot hub /ai home page (1280x900, light, zh)."""
import time
import urllib.request

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:7890/ai"
OUT = "docs/reports/shots/hub-ai-recolor.png"

for _ in range(60):
    try:
        if urllib.request.urlopen(URL, timeout=2).status == 200:
            break
    except Exception:
        time.sleep(2)
else:
    raise SystemExit("hub /ai not reachable")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(
        viewport={"width": 1280, "height": 900},
        color_scheme="light",
        locale="zh-CN",
    )
    page.goto(URL, wait_until="load")
    page.wait_for_timeout(4000)
    page.screenshot(path=OUT)
    browser.close()
print("saved", OUT)
