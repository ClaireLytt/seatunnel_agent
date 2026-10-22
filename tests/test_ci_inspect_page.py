"""Browser tests for the React /ciinspect page.

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_secret_scan_page.py. Deselected by default:

    pytest -m uitest tests/test_ci_inspect_page.py

Equivalence coverage for the retired uitest YAML case
(cases/devops.yaml CI1, removed in this ticket): pasting a failing job
log and clicking Analyze yields a triage report with the root-cause
cluster — test_ci_inspect_failing_log reuses CI1's sample log verbatim
and asserts the same signals (title, ConnectionError, error events 2,
root-cause clusters) on the zh page CI1 exercised.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.devops.ci_inspect.manifest import MANIFEST
from tests.conftest import make_page_url
from tests.conftest import zh_page as _zh_page

SHOTS = Path(__file__).resolve().parents[1] / "runs" / "shots"

# The CI1 yaml case's sample log, verbatim.
FAILING_LOG = (
    "##[error]ConnectionError: reach host:443 after 3 retries\n"
    "##[error]ConnectionError: reach host:443 after 5 retries"
)

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.devops.ci_inspect.api:router",
    "/ciinspect")


@pytest.mark.uitest
def test_ci_inspect_page_smoke(page_url):
    """English chrome: title, log input, Analyze button; no console
    errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role(
            "heading", name="CI Log Triage")).to_be_visible()
        expect(page.get_by_placeholder(
            "Paste one job's log (GitHub Actions timestamps are "
            "fine)…")).to_be_visible()
        expect(page.get_by_role(
            "button", name="Analyze", exact=True)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_ci_inspect_failing_log(page_url):
    """CI1 equivalent: paste a failing job log on the zh page, Analyze,
    and the report region shows the triage (title, the clustered
    ConnectionError, the 2 error events, the root-cause section)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(lambda: browser.new_context(), page_url)

        page.get_by_placeholder(
            "粘贴一个作业的日志(带 GitHub Actions 时间戳也可以)…").fill(
            FAILING_LOG)
        page.get_by_role("button", name="分析", exact=True).click()

        report = page.locator(".ci-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("CI 日志诊断")
        expect(report).to_contain_text("ConnectionError")
        expect(report).to_contain_text("错误事件 2")
        expect(report).to_contain_text("根因聚类")
        browser.close()


@pytest.mark.uitest
def test_ci_inspect_empty_input_warns(page_url):
    """Empty input shows the localized warning instead of a report."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Analyze", exact=True).click()
        expect(page.get_by_text(
            "Paste a log or runs JSON first.")).to_be_visible()
        expect(page.locator(".ci-report")).to_have_count(0)
        browser.close()


@pytest.mark.uitest
def test_ci_inspect_screenshots(page_url):
    """en-dark and zh-light-with-report shots for the batch report
    (written under runs/shots/)."""
    from playwright.sync_api import expect, sync_playwright

    SHOTS.mkdir(parents=True, exist_ok=True)
    host = urlparse(page_url).hostname

    with sync_playwright() as p:
        browser = p.chromium.launch()

        ctx = browser.new_context(viewport={"width": 1280, "height": 900},
                                  color_scheme="dark")
        ctx.add_cookies([{"name": "st-lang", "value": "en",
                          "domain": host, "path": "/"}])
        page = ctx.new_page()
        page.goto(page_url, wait_until="networkidle")
        expect(page.locator("h1")).to_contain_text("CI Log Triage")
        page.screenshot(path=str(SHOTS / "ciinspect-react-en-dark.png"),
                        full_page=True)
        ctx.close()

        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = _zh_page(lambda: ctx, page_url)
        expect(page.locator("h1")).to_contain_text("CI 日志诊断")
        page.get_by_placeholder(
            "粘贴一个作业的日志(带 GitHub Actions 时间戳也可以)…").fill(
            FAILING_LOG)
        page.get_by_role("button", name="分析", exact=True).click()
        expect(page.locator(".ci-report")).to_be_visible(timeout=15000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(SHOTS / "ciinspect-react-zh-report.png"),
                        full_page=True)
        browser.close()
