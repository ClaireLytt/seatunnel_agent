"""Screenshot the old Gradio /impact page (en/zh x light/dark)."""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:7863"

with sync_playwright() as p:
    browser = p.chromium.launch()
    for lang in ("en", "zh"):
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        ctx.add_cookies([{"name": "st-lang", "value": lang,
                          "url": BASE}])
        for theme in ("light", "dark"):
            page = ctx.new_page()
            page.goto(f"{BASE}/impact?__theme={theme}", wait_until="load")
            page.wait_for_timeout(3000)
            name = f"old_{lang}_{theme}.png"
            page.screenshot(path=str(OUT / name), full_page=True)
            print("saved", name)
            page.close()
        ctx.close()
    browser.close()
