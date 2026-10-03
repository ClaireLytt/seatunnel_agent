# -*- coding: utf-8 -*-
"""Notify channel: payload shapes, kind detection, send(), CLI integration."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.notify import build_payload, detect_kind, send

DEMO_CI = Path(__file__).resolve().parents[1] / "examples" / "ciinspect_demo"
DEMO_COST = (Path(__file__).resolve().parents[1] / "examples"
             / "llmcost_demo" / "llm_usage_sample.jsonl")


class TestPayloads:
    def test_shapes(self):
        assert build_payload("dingtalk", "T", "x")["msgtype"] == "markdown"
        assert build_payload("feishu", "T", "x")["msg_type"] == "text"
        assert "*T*" in build_payload("slack", "T", "x")["text"]
        assert build_payload("generic", "T", "x") == {"title": "T",
                                                      "text": "x"}

    def test_detect_kind(self):
        assert detect_kind("https://oapi.dingtalk.com/robot/send?x") == "dingtalk"
        assert detect_kind("https://open.feishu.cn/open-apis/bot/v2/hook/x") == "feishu"
        assert detect_kind("https://hooks.slack.com/services/x") == "slack"
        assert detect_kind("https://example.com/hook") == "generic"


class TestSend:
    def test_send_via_transport(self, monkeypatch):
        sent = {}

        def transport(url, body):
            sent["url"], sent["body"] = url, json.loads(body)
        ok = send("T", "msg", url="https://oapi.dingtalk.com/x",
                  transport=transport)
        assert ok and sent["url"].endswith("/x")
        assert sent["body"]["msgtype"] == "markdown"  # kind auto-detected

    def test_no_url_returns_false(self, monkeypatch):
        monkeypatch.delenv("NOTIFY_WEBHOOK_URL", raising=False)
        assert send("T", "msg") is False

    def test_transport_failure_swallowed(self):
        def boom(url, body):
            raise RuntimeError("down")
        assert send("T", "msg", url="https://x", transport=boom) is False

    def test_env_configuration(self, monkeypatch):
        sent = {}
        monkeypatch.setenv("NOTIFY_WEBHOOK_URL", "https://example.com/h")
        monkeypatch.setenv("NOTIFY_KIND", "slack")
        assert send("T", "m", transport=lambda u, b: sent.update(
            body=json.loads(b)))
        assert "*T*" in sent["body"]["text"]


class TestCliIntegration:
    def test_ciinspect_notify_on_flaky(self, monkeypatch):
        alerts = []
        monkeypatch.setattr("seatunnel_agent.notify.send",
                            lambda title, text, **kw: alerts.append(
                                (title, text)) or True)
        r = CliRunner().invoke(cli, [
            "ciinspect", "--runs", str(DEMO_CI / "runs.json"), "--notify"])
        assert r.exit_code == 0, r.output
        assert alerts and "flaky" in alerts[0][0].lower()
        assert "abc1234" in alerts[0][1]

    def test_llmcost_notify_on_anomaly(self, monkeypatch, tmp_path):
        alerts = []
        monkeypatch.setattr("seatunnel_agent.notify.send",
                            lambda title, text, **kw: alerts.append(
                                (title, text)) or True)
        monkeypatch.setenv("SEATUNNEL_PRICING_PATH",
                           str(tmp_path / "absent.yaml"))
        r = CliRunner().invoke(cli, [
            "llmcost", "--days", "36500", "--usage-path", str(DEMO_COST),
            "--notify"])
        assert r.exit_code == 0, r.output
        assert alerts and "2026-09-29" in alerts[0][1]  # the demo anomaly day

    def test_no_alert_when_clean(self, monkeypatch, tmp_path):
        alerts = []
        monkeypatch.setattr("seatunnel_agent.notify.send",
                            lambda *a, **kw: alerts.append(a) or True)
        runs = tmp_path / "runs.json"
        runs.write_text('[{"workflow":"w","conclusion":"success",'
                        '"head_sha":"aaaa1111","duration_s":10}]',
                        encoding="utf-8")
        r = CliRunner().invoke(cli, ["ciinspect", "--runs", str(runs),
                                     "--notify"])
        assert r.exit_code == 0, r.output
        assert alerts == []
