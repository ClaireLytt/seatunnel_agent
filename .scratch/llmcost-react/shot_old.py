"""Screenshot the old Gradio /llmcost page (before React migration)."""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "docs" / "reports" / "shots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:7881"

with sync_playwright() as p:
    browser = p.chromium.launch()
    for lang, theme, name in (
        ("en", "dark", "llmcost-gradio-before-en-dark.png"),
        ("zh", "light", "llmcost-gradio-before-zh-light.png"),
    ):
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        ctx.add_cookies([{"name": "st-lang", "value": lang, "url": BASE}])
        page = ctx.new_page()
        page.goto(f"{BASE}/llmcost?__theme={theme}", wait_until="load")
        page.wait_for_timeout(4000)  # charts render after load callback
        page.screenshot(path=str(OUT / name), full_page=True)
        print("saved", name)
        ctx.close()

    # zh: price accordion opened
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_cookies([{"name": "st-lang", "value": "zh", "url": BASE}])
    page = ctx.new_page()
    page.goto(f"{BASE}/llmcost", wait_until="load")
    page.wait_for_timeout(4000)
    page.get_by_role("button", name="价格表 ▼").click()
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT / "llmcost-gradio-before-zh-prices.png"),
                    full_page=True)
    print("saved llmcost-gradio-before-zh-prices.png")
    browser.close()
