"""Shared test fixtures."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

# Redirect the text2sql example store OUT of the repo before any test module
# imports examples.py (its default path is read at import time). Without this,
# every full pytest run rewrites config/t2s_examples.json (id/timestamp churn)
# and dirties the working tree — see docs/pitfalls.md 2026-10-17/18.
_T2S_TMP = Path(tempfile.mkdtemp(prefix="t2s_examples_")) / "t2s_examples.json"
os.environ.setdefault("T2S_EXAMPLES_PATH", str(_T2S_TMP))


# ── shared Playwright helpers (importable: from tests.conftest import …) ──


def download_text(download) -> str:
    """Save a Playwright download and read it back as text."""
    return Path(download.path()).read_text(encoding="utf-8")


def labeled_select(page, label: str):
    """Locator for the <select> that directly follows the visible label
    text. The React pages render ``<label>…</label><select>`` without
    id/for hooks, so anchor on the label instead of positional nth()."""
    return page.get_by_text(label, exact=True).locator(
        "xpath=following-sibling::select")


def assert_dialect_switch(page, *, dialect: str, run, report,
                          contains: str | None = None,
                          timeout: int = 15000, select=None) -> None:
    """Shared ticket-05 dialect-switch body: select a non-default dialect,
    assert the value stuck, run the page's action (``run()`` does the
    fills/clicks and any page-specific assertions), then assert the report
    rendered with no traceback."""
    from playwright.sync_api import expect

    sel = select if select is not None else page.locator("select").first
    sel.select_option(dialect)
    expect(sel).to_have_value(dialect)
    run()
    expect(report).to_be_visible(timeout=timeout)
    if contains is not None:
        expect(report).to_contain_text(contains)
    expect(page.locator("body")).not_to_contain_text("Traceback")


# ── shared i18n parity helpers (ticket: tests-slim-down 01) ────────────────
#
# Every tests/test_*_i18n.py used to carry identical copies of the trio
# below (~30 lines each). An i18n test file now keeps only its path
# constants and calls:
#
#     res = i18n_resources(I18N_TS)
#     sources = workspace_sources(SRC)


def parse_locale_block(block: str) -> dict[str, str]:
    """Parse one locale's ``translation: {…}`` body from i18n.ts.

    Keys may be multi-part string concatenations ('a ' + 'b'); join them."""
    import re

    pairs = re.findall(
        r"(\w+):\s*((?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|\s|\+)+)",
        block,
    )
    out: dict[str, str] = {}
    for key, raw in pairs:
        chunks = re.findall(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"", raw)
        val = "".join(a if a else b for a, b in chunks)
        out[key] = (val.replace("\\'", "'").replace('\\"', '"')
                    .replace("\\n", "\n"))
    return out


def i18n_resources(i18n_ts: Path) -> dict[str, dict[str, str]]:
    """Extract the en/zh translation dicts from a workspace's i18n.ts."""
    import re

    text = i18n_ts.read_text(encoding="utf-8")
    locales = re.findall(
        r"^  (en|zh): \{\s*translation: \{(.*?)^    \},\s*^  \},",
        text,
        re.S | re.M,
    )
    assert {name for name, _ in locales} == {"en", "zh"}, "en/zh blocks not found"
    return {name: parse_locale_block(body) for name, body in locales}


def workspace_sources(src: Path) -> list[str]:
    """Read every .tsx source in a workspace's src/ dir."""
    files = list(src.glob("*.tsx"))
    assert files, "no .tsx files found — glob broken?"
    return [f.read_text(encoding="utf-8") for f in files]


# ── shared fake-LLM reply builders + CLI runner (ticket: tests-slim-down 03)


def llm_text(reply: str, *, raw_content: Any = None, usage: Any = None):
    """A no-tool-use LLMResponse carrying only ``reply`` text."""
    from seatunnel_agent.common.llm import LLMResponse

    return LLMResponse(wants_tool_use=False, tool_calls=[], thinking_text="",
                       reply_text=reply,
                       raw_content={"f": 1} if raw_content is None else raw_content,
                       usage={} if usage is None else usage)


def llm_tool(name: str, inp: dict, cid: str = "c1", *,
             raw_content: Any = None, usage: Any = None):
    """An LLMResponse requesting one tool call ``name(inp)``."""
    from seatunnel_agent.common.llm import LLMResponse, ToolCall

    return LLMResponse(wants_tool_use=True,
                       tool_calls=[ToolCall(id=cid, name=name, input=inp)],
                       thinking_text="", reply_text="",
                       raw_content={"f": 1} if raw_content is None else raw_content,
                       usage={} if usage is None else usage)


def run_cli(args):
    """Invoke the seatunnel-agent click CLI in-process."""
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    return CliRunner().invoke(cli, args)


# ── React page-test server factory (ticket: arch-deepen-2 C1) ─────────────
#
# Every tests/test_*_page.py used to carry its own _free_port / uvicorn
# page_url fixture / _zh_page copy (~50 lines each). The shared factory
# below is the single implementation; a page-test file declares:
#
#     page_url = make_page_url(MANIFEST, "my.pkg.api:router", "/route")
#
# Options cover the variants the 25 files proved necessary: extra env,
# the no-LLM-key neutralization triple, and chdir-to-tmp/repo-root.


def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_page_url(manifest, router_ref: str, mount: str, *,
                  env: dict[str, str] | None = None,
                  neutralize_llm: bool = False,
                  chdir: str | None = None,
                  extra_mounts: list[tuple[str, Any]] | None = None,
                  post_setup: Callable[..., None] | None = None,
                  name: str = "page_url"):
    """Build the in-process uvicorn ``page_url`` fixture for a React page.

    ``router_ref`` is "module.path:attr" (imported lazily so collection
    stays cheap). ``env`` entries are set via monkeypatch; a value of
    ``None`` deletes the variable instead. ``neutralize_llm`` applies the
    no-key triple (env keys, settings store path, dotenv stubs).
    ``chdir`` is "tmp" or "root" (repo root), or None to stay put.
    ``extra_mounts`` mounts additional built dists ``(mount_path,
    manifest)`` on the same server (skipped when not built, matching the
    historical inline behavior). ``post_setup(monkeypatch, tmp_path)``
    runs after env handling and before the app is assembled — the hook
    for module-level store/agent stubbing and data seeding. ``name``
    names the fixture (for a second server fixture in the same file)."""
    import importlib
    import threading
    import time

    root = Path(__file__).resolve().parents[1]

    @pytest.fixture(name=name)
    def page_url(monkeypatch, tmp_path):
        import uvicorn
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles

        from seatunnel_agent.hub.registry import frontend_dist

        mod_name, attr = router_ref.split(":")
        router = getattr(importlib.import_module(mod_name), attr)

        dist = root / frontend_dist(manifest)
        if not (dist / "index.html").is_file():
            pytest.skip(f"frontend dist not built for {manifest.name} "
                        "(cd frontend && npm run build)")

        if chdir == "tmp":
            monkeypatch.chdir(tmp_path)
        elif chdir == "root":
            monkeypatch.chdir(root)
        if neutralize_llm:
            for var in ("API_KEY", "ANTHROPIC_API_KEY"):
                monkeypatch.delenv(var, raising=False)
            monkeypatch.setenv("SEATUNNEL_LLM_SETTINGS_PATH",
                               str(tmp_path / "no_settings.json"))
            monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
            monkeypatch.setattr(
                "seatunnel_agent.common.config.load_dotenv",
                lambda *a, **k: None)
        for key, value in (env or {}).items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(
                    key, value.replace("{tmp}", str(tmp_path)))
        if post_setup is not None:
            post_setup(monkeypatch, tmp_path)

        app = FastAPI()
        app.include_router(router)
        app.mount(mount, StaticFiles(directory=dist, html=True))
        for extra_mount, extra_manifest in (extra_mounts or []):
            extra_dist = root / frontend_dist(extra_manifest)
            if (extra_dist / "index.html").is_file():
                app.mount(extra_mount,
                          StaticFiles(directory=extra_dist, html=True))

        port = _free_port()
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="warning"))
        t = threading.Thread(target=server.run, daemon=True)
        t.start()
        deadline = time.time() + 15
        while not server.started:
            if time.time() > deadline:
                pytest.fail("uvicorn did not start")
            time.sleep(0.1)
        yield f"http://127.0.0.1:{port}{mount}/"
        server.should_exit = True
        t.join(timeout=5)

    return page_url


def zh_page(ctx_factory, page_url):
    """New page with the st-lang=zh-CN cookie set (Chinese chrome)."""
    from urllib.parse import urlparse

    host = urlparse(page_url).hostname
    ctx = ctx_factory()
    ctx.add_cookies([{"name": "st-lang", "value": "zh-CN",
                      "domain": host, "path": "/"}])
    page = ctx.new_page()
    page.goto(page_url, wait_until="networkidle")
    return page


@pytest.fixture(autouse=True)
def _no_llm_usage_log(monkeypatch):
    """Tests must not append to the real logs/llm_usage.jsonl.

    test_llm_usage re-enables recording by deleting the var and pointing
    LLM_USAGE_PATH at a tmp file."""
    monkeypatch.setenv("LLM_USAGE_LOG", "0")
    monkeypatch.setenv("PROMPT_LAB_LOG", "0")
    monkeypatch.setenv("LLM_EVAL_LOG", "0")
    monkeypatch.setenv("ORCH_CHAT_LOG", "0")
