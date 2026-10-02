# -*- coding: utf-8 -*-
"""Secret scanner: rules, masking, suppression, dir walk, CLI gate, API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.secret_scan import (
    ScanConfig,
    check_fail,
    load_config,
    mask,
    render_markdown,
    scan_dir,
    scan_paths,
    scan_text,
)
from seatunnel_agent.secret_scan.rules import entropy_hit, is_placeholder

DEMO = Path(__file__).resolve().parents[1] / "examples" / "secretscan_demo"


class TestRules:
    @pytest.mark.parametrize("line,rule_id,sev", [
        ("key = AKIAIOSFODNN7EXAMPLE", "aws_access_key", "high"),
        ('aws_secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"',
         "aws_secret_key", "high"),
        ("token: ghp_" + "a1B2" * 9, "github_token", "high"),
        ("t = glpat-ABCDEFGHIJ1234567890", "gitlab_pat", "high"),
        ("slack: xoxb-1234567890-abcdefghij", "slack_token", "high"),
        ("ak = LTAI5tAbCdEfGh123456", "aliyun_ak", "high"),
        ("-----BEGIN RSA PRIVATE KEY-----", "private_key", "high"),
        ("jwt = eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.dBjftJeZ4CVP",
         "jwt", "medium"),
        ('password = "hunter2-prod"', "password_assign", "medium"),
        ('api_key: "sk-live-0123456789abcdef"', "apikey_assign", "medium"),
        ("dsn = mysql://root:p4ssw0rd@host:3306/db",
         "url_credentials", "medium"),
    ])
    def test_rule_hits(self, line, rule_id, sev):
        hits = scan_text(line)
        assert any(f.rule_id == rule_id and f.severity == sev
                   for f in hits), hits

    def test_entropy_fallback_and_threshold(self):
        hits = scan_text('seed = "Jk8vQ2xZr5Tn1Wq7Lm4Yp0Bs6Dh3Fg9C"')
        assert [f.rule_id for f in hits] == ["high_entropy"]
        # ordinary words: no hit
        assert scan_text('name = "configuration_directory_path"') == []

    def test_placeholders_filtered(self):
        for line in ('password = "${DB_PASSWORD}"',
                     'api_key: "your-key-here"',
                     'password = "changeme99"',
                     'token = "<insert-token>"'):
            assert scan_text(line) == [], line
        assert is_placeholder("{{ secret }}")
        assert not entropy_hit("short")

    def test_mask_never_echoes_full_secret(self):
        hits = scan_text('password = "hunter2-prod-very-long"')
        assert hits[0].masked == "hunt…ng"
        assert "hunter2-prod-very-long" not in json.dumps(
            [f.to_dict() for f in hits])
        assert mask("abc") == "ab…"


class TestSuppression:
    def test_inline_pragma(self):
        assert scan_text(
            'password = "hunter2-prod"  # secretscan:ignore') == []

    def test_config_ignore_rule_and_path(self, tmp_path):
        (tmp_path / ".secretscan.yaml").write_text(
            "ignore_rules: [password_assign]\n"
            "ignore_paths: ['fixtures/*']\n", encoding="utf-8")
        (tmp_path / "a.yaml").write_text(
            'password = "hunter2-prod"\nak = AKIAIOSFODNN7EXAMPLE\n',
            encoding="utf-8")
        fix = tmp_path / "fixtures"
        fix.mkdir()
        (fix / "b.yaml").write_text("ak = AKIAIOSFODNN7EXAMPLE",
                                    encoding="utf-8")
        result = scan_dir(tmp_path)
        assert [f.rule_id for f in result.findings] == ["aws_access_key"]
        assert result.files_skipped >= 1  # fixtures/b.yaml

    def test_malformed_config_raises(self, tmp_path):
        (tmp_path / ".secretscan.yaml").write_text("- 42", encoding="utf-8")
        with pytest.raises(ValueError):
            load_config(tmp_path)


class TestDirScan:
    def test_demo_fixture(self):
        result = scan_dir(DEMO, config=ScanConfig())
        sev = result.severities
        assert sev == {"high": 4, "medium": 4, "low": 1}, result.to_dict()
        assert result.files_scanned >= 3

    def test_binary_and_big_files_skipped(self, tmp_path):
        (tmp_path / "bin.dat").write_bytes(b"\x00\x01AKIAIOSFODNN7EXAMPLE")
        (tmp_path / "ok.txt").write_text("ak = AKIAIOSFODNN7EXAMPLE",
                                         encoding="utf-8")
        result = scan_dir(tmp_path)
        assert result.files_scanned == 1
        assert result.files_skipped == 1
        assert len(result.findings) == 1

    def test_scan_paths_mixed(self, tmp_path):
        f = tmp_path / "x.env"
        f.write_text('password = "hunter2-prod"', encoding="utf-8")
        result = scan_paths([f])
        assert result.findings[0].file == str(f)

    def test_severity_ordering(self):
        result = scan_dir(DEMO, config=ScanConfig())
        sevs = [f.severity for f in result.findings]
        assert sevs == sorted(sevs, key={"high": 0, "medium": 1,
                                         "low": 2}.get)


class TestReportAndGate:
    def test_markdown_bilingual_and_masked(self):
        result = scan_dir(DEMO, config=ScanConfig())
        zh = render_markdown(result, "zh")
        en = render_markdown(result, "en")
        assert "敏感凭证扫描" in zh and "已脱敏" in zh
        assert "Secret Scan" in en
        assert "wJalrXUtnFEMI/K7MDENG" not in zh  # full secret never echoed

    def test_check_fail_ladder(self):
        result = scan_dir(DEMO, config=ScanConfig())
        assert check_fail(result, "high")
        assert check_fail(result, "low")
        clean = scan_text("nothing here")
        from seatunnel_agent.secret_scan import ScanResult
        assert not check_fail(ScanResult(findings=clean), "low")


class TestCli:
    def test_scan_demo_fail_on_high(self):
        r = CliRunner().invoke(cli, ["secretscan", str(DEMO),
                                     "--fail-on", "high"])
        assert r.exit_code == 1
        assert "敏感凭证扫描" in r.output

    def test_text_json(self):
        r = CliRunner().invoke(cli, [
            "secretscan", "--text", 'password = "hunter2-prod"',
            "-F", "json"])
        assert r.exit_code == 0, r.output
        payload = json.loads(r.output)
        assert payload["severities"]["medium"] == 1

    def test_clean_text_passes_gate(self):
        r = CliRunner().invoke(cli, ["secretscan", "--text", "hello world",
                                     "--fail-on", "low"])
        assert r.exit_code == 0

    def test_requires_input(self):
        r = CliRunner().invoke(cli, ["secretscan"])
        assert r.exit_code != 0


class TestApi:
    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from seatunnel_agent.secret_scan.api import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_scan_endpoint(self):
        resp = self._client().post("/api/secretscan/scan", json={
            "text": 'password = "hunter2-prod"', "lang": "en",
            "report": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["severities"]["medium"] == 1
        assert "Secret Scan" in data["report"]
        assert "hunter2-prod" not in json.dumps(data)  # masked everywhere

    def test_health(self):
        resp = self._client().get("/api/secretscan/health")
        assert resp.json() == {"status": "ok", "agent": "secret_scan"}
