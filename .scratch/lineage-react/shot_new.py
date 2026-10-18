"""Screenshot the new React /lineage page (en/zh x light/dark) + a lint round-trip."""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:7863"

DEMO = None

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
            page.goto(f"{BASE}/lineage/", wait_until="load")
            page.evaluate(
                f"document.documentElement.setAttribute('data-theme', '{theme}')")
            page.wait_for_timeout(800)
            name = f"new_{lang}_{theme}.png"
            page.screenshot(path=str(OUT / name), full_page=True)
            print("saved", name)
            ctx.close()

    # round-trip: build demo graph, query first table, capture graph (zh light)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_cookies([{"name": "st-lang", "value": "zh", "url": BASE}])
    page = ctx.new_page()
    page.goto(f"{BASE}/lineage/", wait_until="load")
    page.get_by_placeholder("包含 *.sql 文件的目录（递归扫描）").fill("examples/lineage_demo")
    page.get_by_role("button", name="构建血缘图").click()
    page.wait_for_timeout(2000)
    page.get_by_role("button", name="查询血缘").click()
    page.wait_for_selector("svg", timeout=15000)
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT / "new_zh_report.png"), full_page=True)
    print("saved new_zh_report.png")
    browser.close()
