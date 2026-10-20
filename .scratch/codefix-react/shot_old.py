"""Screenshot the old Gradio /codefix page (before React migration)."""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "docs" / "reports" / "shots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:7883"

with sync_playwright() as p:
    browser = p.chromium.launch()
    for lang, theme, name in (
        ("en", "dark", "codefix-gradio-before-en-dark.png"),
        ("zh", "light", "codefix-gradio-before-zh-light.png"),
    ):
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        ctx.add_cookies([{"name": "st-lang", "value": lang, "url": BASE}])
        page = ctx.new_page()
        page.goto(f"{BASE}/codefix?__theme={theme}", wait_until="load")
        page.wait_for_timeout(3000)
        page.screenshot(path=str(OUT / name), full_page=True)
        print("saved", name)
        ctx.close()

    # zh: empty-path validation round-trip
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_cookies([{"name": "st-lang", "value": "zh", "url": BASE}])
    page = ctx.new_page()
    page.goto(f"{BASE}/codefix", wait_until="load")
    page.wait_for_timeout(3000)
    page.get_by_role("button", name="开始修复").click()
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT / "codefix-gradio-before-zh-empty.png"),
                    full_page=True)
    print("saved codefix-gradio-before-zh-empty.png")
    browser.close()
