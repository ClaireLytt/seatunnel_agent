# -*- coding: utf-8 -*-
"""GitHub bot: patch parsing, review comment, signature, webhook flow."""

from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from seatunnel_agent.bot import (
    BOT_MARKER,
    create_bot_app,
    parse_patch,
    review_patch,
    verify_signature,
)

_PATCH = """\
diff --git a/etl/report.sql b/etl/report.sql
--- a/etl/report.sql
+++ b/etl/report.sql
@@ -10,2 +10,4 @@
 SELECT 1;
+SELECT a.id, b.name
+FROM dwd_order_df a, dim_user_df b
+WHERE a.ds = '2026-10-01';
 -- end
diff --git a/conf/app.yaml b/conf/app.yaml
--- a/conf/app.yaml
+++ b/conf/app.yaml
@@ -1,2 +1,3 @@
 app:
+  password: "hunter2-prod"
   debug: false
diff --git a/gone.txt b/gone.txt
--- a/gone.txt
+++ /dev/null
@@ -1 +0,0 @@
-old
"""


class TestPatchParsing:
    def test_added_lines_and_numbers(self):
        files = parse_patch(_PATCH)
        by = {f.path: f for f in files}
        assert set(by) == {"etl/report.sql", "conf/app.yaml"}  # deleted file skipped
        sql = by["etl/report.sql"]
        assert sql.added[0] == (11, "SELECT a.id, b.name")
        assert by["conf/app.yaml"].added[0][0] == 2

    def test_empty_patch(self):
        assert parse_patch("") == []


class TestReview:
    def test_findings_and_comment(self):
        findings, comment = review_patch(_PATCH)
        tools = {f.tool for f in findings}
        assert "secret_scan" in tools and "sql_review" in tools
        secret = next(f for f in findings if f.tool == "secret_scan")
        assert secret.path == "conf/app.yaml" and secret.line == 2
        assert "hunter2-prod" not in comment          # masked
        assert comment.startswith(BOT_MARKER)
        assert "seatunnel-agent secretscan" in comment

    def test_clean_patch_no_comment(self):
        findings, comment = review_patch(
            "--- a/x.txt\n+++ b/x.txt\n@@ -1 +1,2 @@\n line\n+hello world\n")
        assert findings == [] and comment == ""


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body,
                                hashlib.sha256).hexdigest()


def _payload() -> dict:
    return {"action": "opened",
            "pull_request": {"url": "https://api.github.com/x",
                             "comments_url": "https://api.github.com/c"}}


class TestWebhook:
    def test_signature_helper(self):
        body = b'{"a": 1}'
        sig = _sign("s3cret", body)
        assert verify_signature("s3cret", body, sig)
        assert not verify_signature("s3cret", body, "sha256=deadbeef")
        assert not verify_signature("s3cret", body, None)

    def _client(self, secret="", patch=_PATCH, posted=None,
                existing_url=None, updated=None):
        app = create_bot_app(
            secret=secret,
            fetch_diff=lambda payload: patch,
            post_comment=lambda payload, body: (
                posted if posted is not None else []).append(body),
            find_bot_comment=lambda payload: existing_url,
            update_comment=lambda url, body: (
                updated if updated is not None else []).append((url, body)),
        )
        return TestClient(app)

    def test_bad_signature_401(self):
        client = self._client(secret="s3cret")
        resp = client.post("/webhook", content=b"{}",
                           headers={"X-GitHub-Event": "pull_request",
                                    "X-Hub-Signature-256": "sha256=bad"})
        assert resp.status_code == 401

    def test_ping_and_other_events(self):
        client = self._client()
        assert client.post("/webhook", json={}, headers={
            "X-GitHub-Event": "ping"}).json() == {"status": "pong"}
        resp = client.post("/webhook", json={}, headers={
            "X-GitHub-Event": "issues"})
        assert resp.json()["status"] == "ignored"

    def test_pr_flow_posts_comment(self):
        posted: list[str] = []
        client = self._client(secret="s3cret", posted=posted)
        body = json.dumps(_payload()).encode()
        resp = client.post("/webhook", content=body, headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _sign("s3cret", body)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "reviewed" and data["commented"] is True
        assert posted and BOT_MARKER in posted[0]

    def test_clean_pr_no_comment(self):
        posted: list[str] = []
        client = self._client(patch="--- a/x\n+++ b/x\n@@ -1 +1,2 @@\n a\n+ok\n",
                              posted=posted)
        resp = client.post("/webhook", json=_payload(), headers={
            "X-GitHub-Event": "pull_request"})
        assert resp.json()["commented"] is False
        assert posted == []

    def test_unhandled_action_ignored(self):
        client = self._client()
        payload = {**_payload(), "action": "labeled"}
        resp = client.post("/webhook", json=payload, headers={
            "X-GitHub-Event": "pull_request"})
        assert resp.json()["status"] == "ignored"

    def test_existing_comment_updated_not_duplicated(self):
        posted, updated = [], []
        client = self._client(posted=posted, updated=updated,
                              existing_url="https://api.github.com/c/1")
        resp = client.post("/webhook", json=_payload(), headers={
            "X-GitHub-Event": "pull_request"})
        assert resp.json()["commented"] is True
        assert posted == []                      # no second comment
        assert updated and updated[0][0].endswith("/c/1")
        assert BOT_MARKER in updated[0][1]

    def test_resolved_note_when_findings_clear(self):
        posted, updated = [], []
        clean = ("--- a/x\n+++ b/x\n@@ -1 +1,2 @@\n a\n+ok\n")
        client = self._client(patch=clean, posted=posted, updated=updated,
                              existing_url="https://api.github.com/c/1")
        resp = client.post("/webhook", json=_payload(), headers={
            "X-GitHub-Event": "pull_request"})
        assert resp.json()["commented"] is False
        assert posted == []
        assert updated and "✅" in updated[0][1]

    def test_no_newline_marker_keeps_line_numbers(self):
        patch = ("--- a/x.txt\n+++ b/x.txt\n@@ -1,2 +1,3 @@\n line1\n"
                 "-old\n\\ No newline at end of file\n"
                 "+new2\n+new3\n")
        files = parse_patch(patch)
        assert files[0].added == [(2, "new2"), (3, "new3")]

    def test_fetch_failure_502(self):
        def boom(payload):
            raise RuntimeError("no network")
        app = create_bot_app(fetch_diff=boom,
                             post_comment=lambda p, b: None,
                             find_bot_comment=lambda p: None,
                             update_comment=lambda u, b: None)
        resp = TestClient(app).post("/webhook", json=_payload(), headers={
            "X-GitHub-Event": "pull_request"})
        assert resp.status_code == 502

    def test_health(self):
        assert self._client().get("/health").json() == {
            "status": "ok", "agent": "bot"}


class TestFindBotCommentPagination:
    def test_marker_found_on_second_page(self, monkeypatch):
        from seatunnel_agent.bot import server as srv
        pages = {
            1: [{"body": "x", "url": "u1"}] * 100,
            2: [{"body": srv.BOT_MARKER + " hi", "url": "u-bot"}],
        }

        def fake_request(url, data=None, accept=""):
            import json as _j
            page = int(url.split("&page=")[1])
            return _j.dumps(pages.get(page, [])).encode()
        monkeypatch.setattr(srv, "_gh_request", fake_request)
        payload = {"pull_request": {"comments_url": "https://api/c"}}
        assert srv.default_find_bot_comment(payload) == "u-bot"

    def test_not_found_stops_on_short_page(self, monkeypatch):
        from seatunnel_agent.bot import server as srv
        calls = []

        def fake_request(url, data=None, accept=""):
            calls.append(url)
            return b"[]"
        monkeypatch.setattr(srv, "_gh_request", fake_request)
        payload = {"pull_request": {"comments_url": "https://api/c"}}
        assert srv.default_find_bot_comment(payload) is None
        assert len(calls) == 1


class TestSqlLineMapping:
    def test_second_hunk_finding_gets_real_line(self):
        patch = (
            "--- a/q.sql\n+++ b/q.sql\n"
            "@@ -1,1 +1,2 @@\n SELECT 1;\n+-- harmless comment\n"
            "@@ -50,1 +51,3 @@\n SELECT 2;\n"
            "+SELECT a.id FROM t1 a, t2 b\n"
            "+WHERE a.ds = '2026-01-01';\n")
        findings, _ = review_patch(patch)
        sql = [f for f in findings if f.tool == "sql_review"]
        assert sql, findings
        # the cartesian join sits in the SECOND hunk (new line >= 51)
        assert any(f.line >= 51 for f in sql), [f.to_dict() for f in sql]
