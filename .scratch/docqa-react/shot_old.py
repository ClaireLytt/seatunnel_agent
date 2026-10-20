"""Screenshot the old Gradio /docqa page (before React migration)."""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "docs" / "reports" / "shots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:7882"

with sync_playwright() as p:
    browser = p.chromium.launch()
    for lang, theme, name in (
        ("en", "dark", "docqa-gradio-before-en-dark.png"),
        ("zh", "light", "docqa-gradio-before-zh-light.png"),
    ):
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        ctx.add_cookies([{"name": "st-lang", "value": lang, "url": BASE}])
        page = ctx.new_page()
        page.goto(f"{BASE}/docqa?__theme={theme}", wait_until="load")
        page.wait_for_timeout(3000)
        page.screenshot(path=str(OUT / name), full_page=True)
        print("saved", name)
        ctx.close()

    # zh: deterministic extractive ask round-trip
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_cookies([{"name": "st-lang", "value": "zh", "url": BASE}])
    page = ctx.new_page()
    page.goto(f"{BASE}/docqa", wait_until="load")
    page.wait_for_timeout(3000)
    page.locator("textarea").first.fill("jdbc sink 怎么配置?")
    page.get_by_role("button", name="提问").click()
    page.wait_for_timeout(3000)
    page.screenshot(path=str(OUT / "docqa-gradio-before-zh-answer.png"),
                    full_page=True)
    print("saved docqa-gradio-before-zh-answer.png")
    browser.close()
