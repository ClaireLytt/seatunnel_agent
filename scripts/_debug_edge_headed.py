"""Headed Edge, Chinese UI: run compare-all and LEAVE the window open."""
import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from playwright.sync_api import sync_playwright
from seatunnel_agent.ui_testing.page import DCPage

BASE = "http://127.0.0.1:7860"
errors = []

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge", headless=False)
    page = browser.new_page(viewport={"width": 1366, "height": 768})
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    dc = DCPage(page, BASE)
    dc.goto("/datacompare")
    dc.set_language("中文")

    for side in ("A", "B"):
        dc.clear_box("主机", side=side)
        dc.clear_box("端口", side=side)
        dc.clear_box("数据库", side=side)
        dc.click_button("连接", side=side)
        dc.wait_status(side=side, ok=True, timeout_ms=90000)
        print(f"side {side} connected")

    dc.select_table("dc_test_orders_a", side="A")
    dc.select_table("dc_test_orders_b", side="B")
    print("clicking 全部对比 (zh, headed Edge) ...")
    t0 = time.perf_counter()
    dc.click_button("全部对比")
    dc.wait_result_stable(timeout_ms=240000)
    dt = time.perf_counter() - t0

    text = dc.result_text()
    print(f"finished in {dt:.1f}s, visible text length = {len(text)}")
    print("first 200 chars:", text[:200].replace("\n", " "))
    print("console errors:", errors if errors else "none")
    page.screenshot(path="runs/edge_zh_repro.png", full_page=True)
    print("window stays open for 30 min — 用户可直接接管操作")
    time.sleep(1800)
    browser.close()
