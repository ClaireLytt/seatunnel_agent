"""Screenshot the new React /dagcheck page (after migration)."""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "docs" / "reports" / "shots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:7877"

with sync_playwright() as p:
    browser = p.chromium.launch()

    # en dark (empty form)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_cookies([{"name": "st-lang", "value": "en", "url": BASE}])
    page = ctx.new_page()
    page.goto(f"{BASE}/dagcheck/", wait_until="load")
    page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT / "dagcheck-react-en-dark.png"), full_page=True)
    print("saved dagcheck-react-en-dark.png")
    ctx.close()

    # zh light + report round-trip (demo dir)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_cookies([{"name": "st-lang", "value": "zh", "url": BASE}])
    page = ctx.new_page()
    page.goto(f"{BASE}/dagcheck/", wait_until="load")
    page.get_by_role("button", name="体检 DAG").click()
    page.wait_for_selector(".md-report", timeout=15000)
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "dagcheck-react-zh-report.png"), full_page=True)
    print("saved dagcheck-react-zh-report.png")
    browser.close()
