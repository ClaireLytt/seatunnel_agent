"""Screenshot the old Gradio /orchestrator page (before React migration)."""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "docs" / "reports" / "shots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:7877"

with sync_playwright() as p:
    browser = p.chromium.launch()
    for lang, theme, name in (
        ("en", "dark", "orchestrator-gradio-before-en-dark.png"),
        ("zh", "light", "orchestrator-gradio-before-zh-light.png"),
    ):
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        ctx.add_cookies([{"name": "st-lang", "value": lang, "url": BASE}])
        page = ctx.new_page()
        page.goto(f"{BASE}/orchestrator?__theme={theme}", wait_until="load")
        page.wait_for_timeout(3000)
        page.screenshot(path=str(OUT / name), full_page=True)
        print("saved", name)
        ctx.close()

    # zh, agents accordion opened
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_cookies([{"name": "st-lang", "value": "zh", "url": BASE}])
    page = ctx.new_page()
    page.goto(f"{BASE}/orchestrator", wait_until="load")
    page.wait_for_timeout(3000)
    page.get_by_text("可路由的 agent").click()
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT / "orchestrator-gradio-before-zh-agents.png"),
                    full_page=True)
    print("saved orchestrator-gradio-before-zh-agents.png")
    browser.close()
