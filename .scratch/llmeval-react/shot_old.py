"""Screenshot the old Gradio /llmeval page (before React migration)."""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "docs" / "reports" / "shots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:7878"

with sync_playwright() as p:
    browser = p.chromium.launch()
    for lang, theme, name in (
        ("en", "dark", "llmeval-gradio-before-en-dark.png"),
        ("zh", "light", "llmeval-gradio-before-zh-light.png"),
    ):
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        ctx.add_cookies([{"name": "st-lang", "value": lang, "url": BASE}])
        page = ctx.new_page()
        page.goto(f"{BASE}/llmeval?__theme={theme}", wait_until="load")
        page.wait_for_timeout(3000)
        page.screenshot(path=str(OUT / name), full_page=True)
        print("saved", name)
        ctx.close()

    # zh: load demo + validate round-trip
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_cookies([{"name": "st-lang", "value": "zh", "url": BASE}])
    page = ctx.new_page()
    page.goto(f"{BASE}/llmeval", wait_until="load")
    page.wait_for_timeout(3000)
    page.get_by_role("button", name="载入示例套件").click()
    page.wait_for_timeout(800)
    page.get_by_role("button", name="校验套件(不调 LLM)").click()
    page.wait_for_timeout(1200)
    page.screenshot(path=str(OUT / "llmeval-gradio-before-zh-validate.png"),
                    full_page=True)
    print("saved llmeval-gradio-before-zh-validate.png")
    browser.close()
