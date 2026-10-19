"""Screenshot the old Gradio /migrate page (en)."""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto("http://127.0.0.1:7862/migrate", wait_until="load")
    page.wait_for_timeout(3000)
    page.screenshot(path=str(OUT / "old_en.png"), full_page=True)
    print("saved old_en.png")
    browser.close()
