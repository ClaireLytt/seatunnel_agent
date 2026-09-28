"""Reproduce compare-all in REAL Edge against the live app at 127.0.0.1:7860."""
import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from playwright.sync_api import sync_playwright
from seatunnel_agent.ui_testing.page import DCPage

BASE = "http://127.0.0.1:7860"

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    dc = DCPage(page, BASE)
    dc.goto("/datacompare")

    for side in ("A", "B"):
        dc.clear_box("主机", side=side)
        dc.clear_box("端口", side=side)
        dc.clear_box("数据库", side=side)
        dc.click_button("连接", side=side)
        dc.wait_status(side=side, ok=True, timeout_ms=90000)
        print(f"side {side} connected")

    dc.select_table("dc_test_orders_a", side="A")
    dc.select_table("dc_test_orders_b", side="B")
    print("tables selected, clicking 全部对比 ...")
    t0 = time.perf_counter()
    dc.click_button("全部对比")
    before = ""
    dc.wait_result_stable(timeout_ms=240000)
    dt = time.perf_counter() - t0

    text = dc.result_text()
    print(f"finished in {dt:.1f}s, result text length = {len(text)}")
    print("first 300 chars:", text[:300].replace("\n", " "))
    page.screenshot(path="runs/edge_repro.png", full_page=True)
    print("screenshot: runs/edge_repro.png")
    browser.close()
