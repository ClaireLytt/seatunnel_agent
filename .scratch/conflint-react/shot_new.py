"""Screenshot the new React /conflint page (en/zh x light/dark) + a lint round-trip."""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:7863"

DEMO = """env { job.mode = "BATCH" }
source { FakeSource { row.num = 10 } }
sink { Console { } }
"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    for lang in ("en", "zh"):
        for theme in ("light", "dark"):
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            ctx.add_cookies([
                {"name": "st-lang", "value": lang, "url": BASE},
                {"name": "st-theme", "value": theme, "url": BASE},
            ])
            page = ctx.new_page()
            page.goto(f"{BASE}/conflint/", wait_until="load")
            page.evaluate(
                f"document.documentElement.setAttribute('data-theme', '{theme}')")
            page.wait_for_timeout(800)
            name = f"new_{lang}_{theme}.png"
            page.screenshot(path=str(OUT / name), full_page=True)
            print("saved", name)
            ctx.close()

    # round-trip: fill demo config, click lint, capture report state (zh light)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_cookies([{"name": "st-lang", "value": "zh", "url": BASE}])
    page = ctx.new_page()
    page.goto(f"{BASE}/conflint/", wait_until="load")
    page.fill("textarea", DEMO)
    page.get_by_role("button", name="检查配置").click()
    page.wait_for_selector(".cl-report", timeout=15000)
    page.screenshot(path=str(OUT / "new_zh_report.png"), full_page=True)
    print("saved new_zh_report.png")
    browser.close()
