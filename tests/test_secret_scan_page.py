"""Browser tests for the React /secretscan page.

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_pii_page.py. Deselected by default:

    pytest -m uitest tests/test_secret_scan_page.py

Equivalence coverage for the retired uitest YAML cases
(cases/devops.yaml SEC1/SEC2, removed in this ticket): SEC1 (password
assignment hit with masked preview, plaintext never on the page) maps
to test_secret_scan_password_assignment; SEC2 (directory scan) retired
with the Gradio page — directory scanning is a CLI affair (the REST API
refuses to walk directories), the page shows the CLI command instead.
"""

from __future__ import annotations

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.devops.secret_scan.manifest import MANIFEST

SECRET_TEXT = 'password = "hunter2-prod"'

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.devops.secret_scan.api:router",
    "/secretscan")


@pytest.mark.uitest
def test_secret_scan_page_smoke(page_url):
    """English chrome + CLI hint for directory scans; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading", name="Secret Scan")).to_be_visible()
        expect(page.get_by_role("button", name="Scan", exact=True)).to_be_visible()
        expect(page.get_by_text(
            "seatunnel-agent secretscan --fail-on high")).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_secret_scan_password_assignment(page_url):
    """SEC1: pasted password assignment is reported; preview is masked
    (the plaintext secret never appears in the report — the input textarea
    naturally still holds what was pasted)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_placeholder(
            "Paste a config / env file / code snippet…").fill(SECRET_TEXT)
        page.get_by_role("button", name="Scan", exact=True).click()

        report = page.locator(".secret-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("Password assignment")
        expect(report).not_to_contain_text("hunter2-prod")
        browser.close()


@pytest.mark.uitest
def test_secret_scan_empty_text_warns(page_url):
    """Empty input shows the localized warning, no request is made."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Scan", exact=True).click()
        expect(page.get_by_text("Paste some text first.")).to_be_visible()
        browser.close()
