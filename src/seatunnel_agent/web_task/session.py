# -*- coding: utf-8 -*-
"""Browser session for the web-task agent.

Wraps Playwright behind the four primitives the agent needs — snapshot /
click / fill / goto — with element HANDLES kept server-side and exposed to
the model only as indexes (the model can never inject selectors).  A
same-origin guard confines navigation to the start URL's origin unless the
caller explicitly allows external sites.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

_SNAPSHOT_SELECTOR = ("a[href], button, input, textarea, select, "
                      "[role='button'], [role='link']")
_MAX_ELEMENTS = 60
_TEXT_CAP = 80


def _origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}".lower()


class PlaywrightSession:
    """Real browser; create via ``start()``, always ``close()``."""

    def __init__(self, allow_external: bool = False,
                 headed: bool = False) -> None:
        self.allow_external = allow_external
        self.headed = headed
        self._pw: Any = None
        self._browser: Any = None
        self.page: Any = None
        self._handles: list[Any] = []
        self.origin = ""

    def start(self, url: str) -> None:
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=not self.headed)
        self.page = self._browser.new_page()
        self.origin = _origin(url)
        self.page.goto(url, wait_until="domcontentloaded")

    def close(self) -> None:
        for closer in (lambda: self._browser.close(),
                       lambda: self._pw.stop()):
            try:
                closer()
            except Exception:  # noqa: BLE001 — teardown is best-effort
                pass

    # ── agent primitives ────────────────────────────────────────────────

    def snapshot(self) -> str:
        self.page.wait_for_timeout(400)
        self._handles = []
        lines = [f"URL: {self.page.url}", f"TITLE: {self.page.title()}", ""]
        for el in self.page.query_selector_all(_SNAPSHOT_SELECTOR):
            try:
                if not el.is_visible():
                    continue
            except Exception:  # noqa: BLE001 — detached node
                continue
            idx = len(self._handles)
            self._handles.append(el)
            tag = (el.evaluate("e => e.tagName") or "?").lower()
            text = (el.inner_text() or "").strip()[:_TEXT_CAP]
            ph = (el.get_attribute("placeholder") or "")[:_TEXT_CAP]
            val = ""
            if tag in ("input", "textarea"):
                val = (el.input_value() or "")[:_TEXT_CAP]
            desc = text or ph or (el.get_attribute("aria-label") or "")
            extra = f" value='{val}'" if val else ""
            extra += f" placeholder='{ph}'" if ph and not text else ""
            lines.append(f"[{idx}] <{tag}> {desc}{extra}".rstrip())
            if idx + 1 >= _MAX_ELEMENTS:
                lines.append("…(more elements omitted)")
                break
        return "\n".join(lines)

    def _el(self, index: int) -> Any:
        if not (0 <= int(index) < len(self._handles)):
            raise ValueError(f"no element [{index}] — take a snapshot first")
        return self._handles[int(index)]

    def click(self, index: int) -> str:
        self._el(index).click(timeout=5000)
        self.page.wait_for_timeout(600)
        return f"clicked [{index}]; now at {self.page.url}"

    def fill(self, index: int, text: str) -> str:
        self._el(index).fill(text, timeout=5000)
        return f"filled [{index}]"

    def goto(self, url: str) -> str:
        if not self.allow_external and _origin(url) != self.origin:
            return (f"BLOCKED: {url} is outside the allowed origin "
                    f"{self.origin} (start with allow_external to permit)")
        self.page.goto(url, wait_until="domcontentloaded")
        return f"now at {self.page.url}"
