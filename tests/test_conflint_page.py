"""Browser tests for the React /conflint page (ticket 02).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_config_migrate_page.py. Deselected by default (needs a
browser + built dist):

    pytest -m uitest tests/test_conflint_page.py

Equivalence coverage for the retired uitest YAML cases (cases/conflint.yaml,
removed in this ticket): CFL1 typo did-you-mean suggestions, CFL2 demo
directory graded findings.
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.config_lint.manifest import MANIFEST
from seatunnel_agent.hub.registry import frontend_dist

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / frontend_dist(MANIFEST)
DEMO_DIR = ROOT / "examples" / "conflint_demo"

TYPO_CONF = (
    'source { Jdbc { url="u", driver="d", user="u", password="p", '
    'quary = "SELECT 1" } }\n'
    "sink { Consloe {} }"
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url():
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.data.config_lint.api import router

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip(
            "frontend dist not built (cd frontend && npm run build --workspace config_lint)")

    app = FastAPI()
    app.include_router(router)
    app.mount("/conflint", StaticFiles(directory=FRONTEND_DIST, html=True))

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                           log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    deadline = time.time() + 15
    while not server.started:
        if time.time() > deadline:
            pytest.fail("uvicorn did not start")
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}/conflint/"
    server.should_exit = True
    t.join(timeout=5)


@pytest.mark.uitest
def test_conflint_page_smoke(page_url):
    """Page loads: heading, config textarea, dir accordion; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="SeaTunnel Config Lint")).to_be_visible()
        expect(page.locator("textarea")).to_be_visible()
        expect(page.get_by_role("button", name="Lint config",
                                exact=True)).to_be_visible()
        # dir accordion collapsed by default; its fields appear on open
        expect(page.get_by_text("Lint a directory")).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_conflint_typo_suggestions(page_url):
    """CFL1: misspelled param/connector get did-you-mean suggestions."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("textarea").fill(TYPO_CONF)
        page.get_by_role("button", name="Lint config", exact=True).click()

        report = page.locator(".cl-report")
        expect(report).to_be_visible()
        # markdown turns backticks into <code>; text content has no backticks
        expect(report).to_contain_text("did you mean query")
        expect(report).to_contain_text("did you mean Console")
        browser.close()


@pytest.mark.uitest
def test_conflint_directory_batch(page_url):
    """CFL2: demo directory lints to batch stats (3 files, 1 passes)."""
    from playwright.sync_api import expect, sync_playwright

    assert DEMO_DIR.is_dir(), f"demo dir missing: {DEMO_DIR}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_text("Lint a directory").click()
        page.get_by_placeholder(
            "Directory containing *.conf (scanned recursively), "
            "e.g. examples/conflint_demo").fill(str(DEMO_DIR))
        page.get_by_role("button", name="Lint directory", exact=True).click()

        report = page.locator(".cl-report")
        expect(report).to_be_visible()
        # demo dir = 3 files, 1 passes / 2 with findings
        expect(report).to_contain_text("files 3")
        expect(report).to_contain_text("pass 1")
        browser.close()


@pytest.mark.uitest
def test_conflint_empty_input_warning(page_url):
    """Lint with no config shows the localized empty warning, no API call crash."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Lint config", exact=True).click()
        expect(page.get_by_text("Paste a config first.")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_conflint_bad_dir_zh(page_url):
    """Directory lint with a non-directory shows the localized bad_dir error."""
    from urllib.parse import urlparse

    from playwright.sync_api import expect, sync_playwright

    host = urlparse(page_url).hostname

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        ctx.add_cookies([{"name": "st-lang", "value": "zh-CN",
                          "domain": host, "path": "/"}])
        page = ctx.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_text("检查整个目录").click()
        page.get_by_placeholder(
            "包含 *.conf 的目录（递归扫描），如 examples/conflint_demo").fill(
            str(ROOT / "no_such_dir_xyz"))
        page.get_by_role("button", name="检查目录", exact=True).click()

        expect(page.get_by_text("不是有效目录")).to_be_visible()
        expect(page.get_by_text("no_such_dir_xyz")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_conflint_lang_switch(page_url):
    """st-lang cookie drives the chrome language (shared lang.ts), and the
    report follows the UI language through the API lang parameter."""
    from urllib.parse import urlparse

    from playwright.sync_api import expect, sync_playwright

    host = urlparse(page_url).hostname

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # default (no cookie) → English chrome
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        expect(page.get_by_role("button", name="Lint config",
                                exact=True)).to_be_visible()

        # st-lang=zh-CN cookie (set by the hub) → Chinese chrome + zh report
        ctx = browser.new_context()
        ctx.add_cookies([{"name": "st-lang", "value": "zh-CN",
                          "domain": host, "path": "/"}])
        zh_page = ctx.new_page()
        zh_page.goto(page_url, wait_until="networkidle")
        expect(zh_page.get_by_role("button", name="检查配置",
                                   exact=True)).to_be_visible()
        expect(zh_page.locator("textarea")).to_have_attribute(
            "placeholder", "粘贴 SeaTunnel .conf 配置…")

        zh_page.locator("textarea").fill(TYPO_CONF)
        zh_page.get_by_role("button", name="检查配置", exact=True).click()
        expect(zh_page.locator(".cl-report")).to_contain_text("是不是想写")
        browser.close()
