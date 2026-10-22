"""Browser smoke for the React Text2SQL page (ticket #64).

Serves the built dist + the real text2sql router in-process and drives a
real connect against a temp SQLite DB. Deselected by default:

    pytest -m uitest tests/test_t2s_page.py
"""

from __future__ import annotations

import sqlite3
import threading

import pytest

from tests.conftest import download_text as _download_text
from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.text2sql.manifest import MANIFESTS

MANIFEST = MANIFESTS[0]  # the /text2sql card (aux pages share its dist)

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.text2sql.api:router", "/text2sql")


@pytest.fixture()
def db_path(tmp_path) -> str:
    """Temp SQLite demo DB for the real-connect tests."""
    db = tmp_path / "demo.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, amount REAL)")
    con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    con.commit()
    con.close()
    return str(db)


@pytest.mark.uitest
def test_t2s_page_connects(page_url, db_path):
    from playwright.sync_api import expect, sync_playwright

    url = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        expect(page.get_by_role("heading", name="Text2SQL · Chat BI")).to_be_visible()
        # sqlite path: only the database field is shown
        page.locator("#ds").select_option("sqlite")
        expect(page.get_by_text("Host")).not_to_be_visible()
        page.get_by_label("Database").fill(db_path)
        page.get_by_role("button", name="Connect").click()

        status = page.locator(".st-connect-status")
        expect(status).to_contain_text("Connected", timeout=20000)
        expect(status).to_contain_text("2 tables")
        # connected session opens the chat panel (#65)
        expect(page.get_by_role("button", name="Send")).to_be_visible()

        browser.close()


def _fake_agent_setup(monkeypatch, tmp_path):
    """Fake the agent so the chat stream (not the LLM) is the seam under
    test (used by the second server fixture, ``chat_page_url``)."""
    from seatunnel_agent.agents.data.text2sql import api as t2s_api
    from seatunnel_agent.agents.data.text2sql import api_shared as t2s_shared

    class FakeAgent:
        def __init__(self):
            self._on_event = None
            self.runtime = type("R", (), {"ds_type": "sqlite"})()
            self.runtime.store = type(
                "S", (), {"tables": [type("T", (), {"full_name": "orders"})()]})()
            # feedback endpoint touchpoints (qlog + example store), stubbed
            self.runtime.source = "api"
            self.runtime.logger = type(
                "L", (), {"log": lambda self, *a, **k: None})()
            self.example_store = type(
                "E", (), {"add": lambda self, *a, **k: None,
                          "remove_by_question": lambda self, *a, **k: None})()

        def set_event_hook(self, cb):
            self._on_event = cb

        def chat(self, message):
            if "slow" in message:
                # never finishes on its own: the Stop endpoint injects
                # the terminal event into the live stream (sessions.stop).
                # The 60s is only a backstop so the daemon worker thread
                # cannot linger forever; no test ever waits on it.
                self._on_event("text", {"text": "thinking slowly"})
                threading.Event().wait(60)
                return ""
            self._on_event("text", {"text": "looking at orders"})
            rows = [[f"r{i}", i] for i in range(60)]
            self._on_event("tool_result", {
                "name": "execute_sql",
                "result": {"sql": "SELECT region, amount FROM orders",
                           "columns": ["region", "amount"], "rows": rows,
                           "row_count": 60}})
            self._on_event("final_answer", {"text": "orders has 42 rows"})
            return "orders has 42 rows"

    # api.py binds build_agent by value at import time — patch both modules
    monkeypatch.setattr(t2s_shared, "build_agent", lambda *a, **k: FakeAgent())
    monkeypatch.setattr(t2s_api, "build_agent", lambda *a, **k: FakeAgent())


chat_page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.text2sql.api:router", "/text2sql",
    post_setup=_fake_agent_setup, name="chat_page_url")


@pytest.mark.uitest
def test_t2s_chat_streams_and_renders_table(chat_page_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(chat_page_url, wait_until="networkidle")

        page.locator("#ds").select_option("sqlite")
        page.get_by_label("Database").fill("whatever.db")
        page.get_by_role("button", name="Connect").click()
        expect(page.locator(".st-connect-status")).to_contain_text(
            "Connected", timeout=15000)

        page.get_by_placeholder("Ask about your data").fill("how many orders?")
        page.get_by_role("button", name="Send").click()

        expect(page.locator(".st-msg-user")).to_contain_text("how many orders?")
        expect(page.locator(".st-msg-bot").first).to_contain_text(
            "looking at orders", timeout=15000)
        table = page.locator(".st-result table")
        expect(table).to_be_visible()
        expect(table).to_contain_text("region")
        expect(table).to_contain_text("r0")
        expect(page.get_by_text("orders has 42 rows")).to_be_visible()

        # ticket #66: pagination for >20 rows, server-detected Recharts chart,
        # client CSV export control
        expect(page.locator(".st-pager")).to_contain_text("1/2")
        # 60 rows exceed auto-detect caps (server returns None) — the manual
        # type override is the behavior under test here
        expect(page.locator(".st-chart")).to_have_count(0)
        page.get_by_label("Chart type").select_option("bar")
        expect(page.locator(".st-chart svg")).to_be_visible()
        expect(page.locator(".st-csv")).to_be_visible()
        page.locator(".st-pager button").nth(1).click()
        expect(table).to_contain_text("r59")

        # new chat clears the transcript
        page.get_by_role("button", name="New chat").click()
        expect(page.locator(".st-msg-user")).to_have_count(0)

        browser.close()


@pytest.mark.uitest
def test_t2s_schema_filter_and_browser(page_url, db_path):
    """Ticket #68: sidebar table filter narrows the session; the #schema
    view lists tables and shows column detail. Real SQLite session."""
    from playwright.sync_api import expect, sync_playwright

    url = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        page.locator("#ds").select_option("sqlite")
        page.get_by_label("Database").fill(db_path)
        page.get_by_role("button", name="Connect").click()
        expect(page.locator(".st-connect-status")).to_contain_text(
            "Connected", timeout=20000)

        # narrow to one table via the filter panel
        panel = page.locator(".st-schema-panel")
        expect(panel).to_contain_text("2/2")
        panel.get_by_role("button").first.click()  # expand
        panel.get_by_role("button", name="None").click()
        panel.get_by_label("orders").check()
        panel.locator(".st-filter-apply").click()
        expect(panel).to_contain_text("1/2", timeout=15000)

        # schema browser view shows the remaining table's columns
        page.get_by_role("link", name="Schema browser").click()
        browser_view = page.locator(".st-schema-browser")
        expect(browser_view).to_contain_text("orders")
        browser_view.get_by_role("button", name="orders").click()
        expect(page.locator(".st-table-detail")).to_contain_text("amount")

        browser.close()


@pytest.mark.uitest
def test_t2s_history_view_qlog(chat_page_url, tmp_path, monkeypatch):
    """Ticket #69: the #history view lists seeded qlog records and clears."""
    from playwright.sync_api import expect, sync_playwright

    from seatunnel_agent.agents.data.text2sql import api_qlog as t2s_qlog
    from seatunnel_agent.agents.data.text2sql.qlog import QueryLogger

    logger = QueryLogger(log_dir=tmp_path)
    logger.log("how many orders", "SELECT count(*) FROM orders", "ok",
               exec_time_ms=7)
    monkeypatch.setattr(t2s_qlog, "_query_logger", lambda: logger)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(chat_page_url + "#history", wait_until="networkidle")

        view = page.locator(".st-history-view")
        expect(view).to_contain_text("how many orders", timeout=15000)
        view.get_by_text("how many orders").click()
        expect(page.locator(".st-qlog-detail")).to_contain_text("count(*)")
        view.get_by_role("button", name="Clear all").click()
        expect(view).not_to_contain_text("how many orders")

        browser.close()


@pytest.mark.uitest
def test_t2s_favorites_view(page_url, t2s_stores):
    from playwright.sync_api import expect, sync_playwright

    t2s_stores.favs.save("top orders", "SELECT * FROM orders LIMIT 10",
                         "show top orders")

    url = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url + "#favorites", wait_until="networkidle")

        view = page.locator(".st-favorites-view")
        expect(view).to_contain_text("top orders", timeout=15000)
        # search filters
        page.get_by_placeholder("Search").fill("nonexistent")
        expect(view).not_to_contain_text("top orders")
        page.get_by_placeholder("Search").fill("")
        expect(view).to_contain_text("top orders")

        browser.close()


@pytest.mark.uitest
def test_t2s_metrics_view(chat_page_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(chat_page_url + "#metrics", wait_until="networkidle")

        view = page.locator(".st-metrics-view")
        expect(view).to_contain_text("Metrics", timeout=15000)

        browser.close()


@pytest.mark.uitest
def test_t2s_boards_view(page_url, t2s_stores):
    from playwright.sync_api import expect, sync_playwright

    url = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url + "#boards", wait_until="networkidle")

        view = page.locator(".st-boards-view")
        expect(view).to_contain_text("Boards", timeout=15000)
        # create a board
        page.get_by_placeholder("New board").fill("test board")
        page.get_by_role("button", name="Create").click()
        expect(view).to_contain_text("test board", timeout=10000)

        browser.close()


@pytest.mark.uitest
def test_t2s_subscriptions_view(page_url, t2s_stores):
    from playwright.sync_api import expect, sync_playwright

    url = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url + "#subscriptions", wait_until="networkidle")

        view = page.locator(".st-subscriptions-view")
        expect(view).to_contain_text("Subscriptions", timeout=15000)
        # open create form
        page.get_by_role("button", name="New").click()
        # both the sub-name and metric-name inputs carry placeholder "Name"
        expect(view.get_by_placeholder("Name").first).to_be_visible()

        browser.close()


# ── ticket 03: button-level coverage for every text2sql control ──────


@pytest.fixture()
def t2s_stores(tmp_path, monkeypatch):
    """Redirect every module-level text2sql store (favorites, boards,
    subscriptions, qlog, saved sessions) into tmp_path so tests never
    touch the real config/ or ~/.seatunnel-agent files."""
    from types import SimpleNamespace

    from seatunnel_agent.agents.data.text2sql import (
        api_boards,
        api_favorites,
        api_qlog,
        api_shared,
        api_subscriptions,
        chat_history,
    )
    from seatunnel_agent.agents.data.text2sql.boards import BoardStore
    from seatunnel_agent.agents.data.text2sql.favorites import FavoritesStore
    from seatunnel_agent.agents.data.text2sql.qlog import QueryLogger
    from seatunnel_agent.agents.data.text2sql.subscriptions import (
        SubscriptionStore,
    )

    favs = FavoritesStore(tmp_path / "favs.json")
    monkeypatch.setattr(api_shared, "fav_store", favs)
    monkeypatch.setattr(api_favorites, "fav_store", favs)
    boards = BoardStore(tmp_path / "boards.json")
    monkeypatch.setattr(api_boards, "_board_store", boards)
    subs = SubscriptionStore(tmp_path / "subs.json")
    monkeypatch.setattr(api_subscriptions, "_sub_store", subs)
    qlog = QueryLogger(log_dir=tmp_path / "qlog")
    monkeypatch.setattr(api_qlog, "_query_logger", lambda: qlog)
    monkeypatch.setattr(chat_history, "HISTORY_DIR", tmp_path / "history")
    chat_history._invalidate_sessions_cache()
    yield SimpleNamespace(favs=favs, boards=boards, subs=subs, qlog=qlog)
    chat_history._invalidate_sessions_cache()


def _connect_fake(page, expect):
    page.locator("#ds").select_option("sqlite")
    page.get_by_label("Database").fill("whatever.db")
    page.get_by_role("button", name="Connect").click()
    expect(page.locator(".st-connect-status")).to_contain_text(
        "Connected", timeout=15000)


@pytest.mark.uitest
def test_t2s_chat_enter_pager_downloads_feedback(chat_page_url, t2s_stores):
    """Enter sends the question; prev-page pager; CSV download, PNG chart
    export (expect_download) and thumbs-up feedback on the result block."""
    from pathlib import Path

    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(chat_page_url, wait_until="networkidle")
        _connect_fake(page, expect)

        # Enter-to-send (no Send click)
        box = page.get_by_placeholder("Ask about your data")
        box.fill("how many orders?")
        box.press("Enter")
        expect(page.locator(".st-msg-user")).to_contain_text("how many orders?")
        table = page.locator(".st-result table")
        expect(table).to_be_visible(timeout=15000)

        # pager: forward then back (prev-page button)
        pager = page.locator(".st-pager")
        pager.locator("button").nth(1).click()
        expect(pager).to_contain_text("2/2")
        expect(table).to_contain_text("r59")
        pager.locator("button").nth(0).click()
        expect(pager).to_contain_text("1/2")
        expect(table).to_contain_text("r0")

        # CSV download: real file, all 60 rows
        with page.expect_download() as dl:
            page.locator(".st-csv").click()
        assert dl.value.suggested_filename == "result.csv"
        csv_text = _download_text(dl.value)
        assert csv_text.splitlines()[0] == "region,amount"
        assert "r59" in csv_text

        # PNG chart export: pick a chart type, then a real binary download
        page.get_by_label("Chart type").select_option("bar")
        expect(page.locator(".st-chart svg")).to_be_visible()
        with page.expect_download() as dl2:
            page.get_by_role("button", name="PNG").click()
        assert dl2.value.suggested_filename == "chart.png"
        png = Path(dl2.value.path()).read_bytes()
        assert png[:4] == b"\x89PNG"

        # thumbs up: state becomes visible and both buttons lock
        page.get_by_title("Good result — save as favorite").click()
        expect(page.get_by_text("Saved", exact=True)).to_be_visible()
        expect(
            page.get_by_title("Bad result — remove example")).to_be_disabled()
        # the positive feedback landed in the (redirected) favorites store
        assert any(f["question"] == "how many orders?"
                   for f in t2s_stores.favs.list())

        browser.close()


@pytest.mark.uitest
def test_t2s_chat_thumbs_down(chat_page_url, t2s_stores):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(chat_page_url, wait_until="networkidle")
        _connect_fake(page, expect)
        box = page.get_by_placeholder("Ask about your data")
        box.fill("how many orders?")
        box.press("Enter")
        expect(page.locator(".st-result table")).to_be_visible(timeout=15000)

        page.get_by_title("Bad result — remove example").click()
        expect(page.get_by_text("Saved", exact=True)).to_be_visible()
        expect(
            page.get_by_title("Good result — save as favorite")
        ).to_be_disabled()
        assert t2s_stores.favs.list() == []
        browser.close()


@pytest.mark.uitest
def test_t2s_chat_stop_interrupts(chat_page_url):
    """Stop while streaming: the turn ends with the stopped marker and the
    Send button comes back."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(chat_page_url, wait_until="networkidle")
        _connect_fake(page, expect)

        box = page.get_by_placeholder("Ask about your data")
        box.fill("slow question")
        box.press("Enter")
        expect(page.locator(".st-msg-bot").first).to_contain_text(
            "thinking slowly", timeout=15000)
        stop = page.get_by_role("button", name="Stop")
        expect(stop).to_be_visible()
        stop.click()
        # the injected terminal event renders the stopped marker
        expect(page.get_by_text("⏹")).to_be_visible(timeout=15000)
        expect(page.get_by_role("button", name="Send")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_t2s_schema_select_all_and_reload(page_url, db_path):
    """Schema panel: select-all restores a narrowed session; reload keeps
    the table list intact."""
    from playwright.sync_api import expect, sync_playwright

    url = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        page.locator("#ds").select_option("sqlite")
        page.get_by_label("Database").fill(db_path)
        page.get_by_role("button", name="Connect").click()
        expect(page.locator(".st-connect-status")).to_contain_text(
            "Connected", timeout=20000)

        panel = page.locator(".st-schema-panel")
        panel.get_by_role("button").first.click()  # expand
        panel.get_by_role("button", name="None").click()
        panel.get_by_label("orders").check()
        panel.locator(".st-filter-apply").click()
        expect(panel).to_contain_text("1/2", timeout=15000)

        # select-all widens back to every table
        panel.get_by_role("button", name="All", exact=True).click()
        panel.locator(".st-filter-apply").click()
        expect(panel).to_contain_text("2/2", timeout=15000)

        # reload re-reads the schema; the table list survives
        panel.get_by_title("Reload schema").click()
        expect(panel).to_contain_text("2/2", timeout=15000)
        expect(panel.get_by_label("users")).to_be_visible()

        browser.close()


@pytest.mark.uitest
def test_t2s_history_refresh_export_delete_resume(chat_page_url, t2s_stores):
    """History view: refresh, qlog.csv download, delete-selected, and
    resume-session into the live chat."""
    from playwright.sync_api import expect, sync_playwright

    from seatunnel_agent.agents.data.text2sql.chat_history import (
        Text2SQLSession,
        now_iso,
        save_t2s_session,
    )

    t2s_stores.qlog.log("first question", "SELECT 1", "ok", exec_time_ms=3)
    t2s_stores.qlog.log("second question", "SELECT 2", "ok", exec_time_ms=4)
    save_t2s_session(Text2SQLSession(
        session_id="saved-1", title="orders chat",
        created_at=now_iso(), updated_at=now_iso(), ds_type="sqlite",
        chat_messages=[{"role": "user", "content": "resumed question"},
                       {"role": "assistant", "content": "resumed answer"}],
        agent_messages=[]))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(chat_page_url, wait_until="networkidle")
        _connect_fake(page, expect)
        page.get_by_role("link", name="History").click()

        view = page.locator(".st-history-view")
        expect(view).to_contain_text("first question", timeout=15000)

        # qlog.csv export: real download with both records
        with page.expect_download() as dl:
            view.get_by_role("link", name="CSV").click()
        assert dl.value.suggested_filename == "qlog.csv"
        csv_text = _download_text(dl.value)
        assert "first question" in csv_text and "second question" in csv_text

        # delete-selected removes only the chosen record
        delete = view.get_by_role("button", name="Delete", exact=True)
        expect(delete).to_be_disabled()
        view.get_by_text("second question").click()
        delete.click()
        expect(view).not_to_contain_text("second question")
        expect(view).to_contain_text("first question")

        # explicit refresh keeps the surviving record listed
        view.get_by_role("button", name="⟳").first.click()
        expect(view).to_contain_text("first question")

        # resume loads the saved transcript into the chat view
        expect(view).to_contain_text("orders chat")
        view.locator(".st-resume").click()
        expect(page.locator(".st-msg-user")).to_contain_text(
            "resumed question", timeout=15000)
        expect(page.get_by_text("resumed answer")).to_be_visible()

        browser.close()


@pytest.mark.uitest
def test_t2s_favorites_rename_delete_refresh(chat_page_url, t2s_stores):
    """Favorites view: rename via the ✎ button (Enter is the editor's
    only commit path; blur cancels), delete, and refresh."""
    from playwright.sync_api import expect, sync_playwright

    t2s_stores.favs.save("top orders", "SELECT * FROM orders LIMIT 10",
                         "show top orders")
    t2s_stores.favs.save("old name", "SELECT 1", "one")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(chat_page_url + "#favorites", wait_until="networkidle")

        view = page.locator(".st-favorites-view")
        expect(view).to_contain_text("old name", timeout=15000)

        # rename: ✎ opens the inline editor. The editor has no commit
        # button — Enter is the only commit path and blur cancels, so
        # cover both: blur first (no-op), then Enter (commit).
        view.locator("tr", has_text="old name").get_by_title("Rename").click()
        # the row text is replaced by the editor, so re-locate inside tbody
        editor = view.locator("tbody input")
        editor.fill("ignored name")
        editor.blur()  # cancel: the typed value must be discarded
        expect(view).to_contain_text("old name")
        expect(view).not_to_contain_text("ignored name")

        view.locator("tr", has_text="old name").get_by_title("Rename").click()
        editor = view.locator("tbody input")
        editor.fill("new name")
        editor.press("Enter")
        expect(view).to_contain_text("new name", timeout=10000)
        expect(view).not_to_contain_text("old name")
        assert any(f["name"] == "new name" for f in t2s_stores.favs.list())

        # delete the other favorite
        view.locator("tr", has_text="top orders").get_by_title(
            "Delete").click()
        expect(view).not_to_contain_text("top orders")

        # refresh re-fetches; the renamed favorite is still there
        view.get_by_role("button", name="⟳").click()
        expect(view).to_contain_text("new name")

        browser.close()


@pytest.mark.uitest
def test_t2s_metrics_expand_and_use(chat_page_url):
    """Metrics view: row expand shows the expression; Use prefills the
    chat input with the metric question."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(chat_page_url, wait_until="networkidle")
        _connect_fake(page, expect)
        page.get_by_role("link", name="Metrics").click()

        view = page.locator(".st-metrics-view")
        expect(view).to_contain_text("销售额", timeout=15000)

        # row expand reveals the metric detail
        view.get_by_text("销售额", exact=True).click()
        expect(view).to_contain_text("SUM(amount)")

        # use-metric jumps back to chat with the question prefilled
        view.locator("tr", has_text="销售额").first.get_by_role(
            "button", name="Use").click()
        box = page.get_by_placeholder("Ask about your data")
        expect(box).to_be_visible(timeout=15000)
        expect(box).to_have_value("Show 销售额 broken down by city")

        browser.close()


@pytest.mark.uitest
def test_t2s_boards_enter_create_render_delete_refresh(page_url, t2s_stores, db_path):
    """Boards view: Enter creates a board; a pinned item renders against
    the live session; delete removes it; refresh confirms."""
    from playwright.sync_api import expect, sync_playwright

    url = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        page.locator("#ds").select_option("sqlite")
        page.get_by_label("Database").fill(db_path)
        page.get_by_role("button", name="Connect").click()
        expect(page.locator(".st-connect-status")).to_contain_text(
            "Connected", timeout=20000)
        page.get_by_role("link", name="Boards").click()

        view = page.locator(".st-boards-view")
        expect(view).to_contain_text("Boards", timeout=15000)

        # Enter in the name box creates the board
        name_box = page.get_by_placeholder("New board name")
        name_box.fill("daily board")
        name_box.press("Enter")
        expect(view).to_contain_text("daily board", timeout=10000)

        # pin an item server-side, refresh picks it up
        board_id = t2s_stores.boards.list()[0]["id"]
        t2s_stores.boards.pin(board_id, "order ids",
                              "SELECT id FROM orders", "sqlite")
        view.get_by_role("button", name="⟳").click()
        expect(view).to_contain_text("1 items", timeout=10000)

        # render runs the pinned SQL in the connected session
        view.get_by_role("button", name="Render").click()
        view.get_by_text("daily board").click()  # expand
        expect(view).to_contain_text("order ids", timeout=15000)
        expect(view.locator("table th", has_text="id")).to_be_visible()

        # delete, then refresh shows the empty marker
        view.get_by_role("button", name="✕").click()
        expect(view).not_to_contain_text("daily board")
        view.get_by_role("button", name="⟳").click()
        expect(view.get_by_text("—")).to_be_visible()

        browser.close()


@pytest.mark.uitest
def test_t2s_subscriptions_lifecycle(chat_page_url, t2s_stores, monkeypatch):
    """Subscriptions: create → disable → enable → run-now → delete, all
    through the UI (the runner itself is stubbed deterministic)."""
    from playwright.sync_api import expect, sync_playwright

    from seatunnel_agent.agents.data.text2sql import api_subscriptions

    def fake_run(sub, store):
        store.record_run(sub["id"], "ok")

    monkeypatch.setattr(api_subscriptions, "run_subscription", fake_run)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(chat_page_url + "#subscriptions", wait_until="networkidle")

        view = page.locator(".st-subscriptions-view")
        expect(view).to_contain_text("Subscriptions", timeout=15000)

        # create: name + metric, keep the default cron
        page.get_by_role("button", name="New").click()
        view.get_by_placeholder("Name").first.fill("daily sales")
        view.get_by_placeholder("Name").nth(1).fill("sales_amount")
        view.get_by_role("button", name="New", exact=True).click()
        row = view.locator("tbody tr", has_text="daily sales")
        expect(row).to_be_visible(timeout=10000)
        expect(row).to_contain_text("—")  # enabled, never run

        # toggle: disable then re-enable
        row.get_by_title("Disable").click()
        expect(row).to_contain_text("disabled", timeout=10000)
        row.get_by_title("Enable").click()
        expect(row).not_to_contain_text("disabled")

        # run-now records a run; the status column reflects it
        row.get_by_title("Run now").click()
        expect(row).to_contain_text("ok", timeout=10000)

        # ⟳ re-fetches the list; the recorded run status survives
        view.get_by_role("button", name="⟳").click()
        row = view.locator("tbody tr", has_text="daily sales")
        expect(row).to_contain_text("ok", timeout=10000)

        # delete closes the loop
        row.get_by_role("button", name="✕").click()
        expect(view).not_to_contain_text("daily sales")
        assert t2s_stores.subs.list() == []

        browser.close()


@pytest.mark.uitest
def test_t2s_template_chip_prefills_question(chat_page_url):
    """Clicking a template chip prefills the chat input with its hint."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(chat_page_url, wait_until="networkidle")
        _connect_fake(page, expect)

        bar = page.locator(".st-template-bar")
        chip = bar.get_by_role("button", name="Month-over-Month")
        expect(chip).to_be_visible(timeout=15000)
        chip.click()
        expect(page.get_by_placeholder("Ask about your data")).to_have_value(
            "Use the Month-over-Month pattern to analyze ")

        browser.close()
