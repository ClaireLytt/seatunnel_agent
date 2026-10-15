# -*- coding: utf-8 -*-
"""Unit tests for the uitest adhoc command (no browser, no tokens)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from seatunnel_agent.agents.devops.ui_testing import adhoc as ah
from seatunnel_agent.agents.devops.ui_testing.__main__ import main
from seatunnel_agent.agents.devops.ui_testing.loader import CaseLoadError
from seatunnel_agent.agents.devops.ui_testing.models import CaseResult, StepLog


# ── load_adhoc_case ──

class TestLoadAdhocCase:
    def test_bare_step_list(self, tmp_path):
        f = tmp_path / "s.yaml"
        f.write_text("- click: 连接\n- wait_status_ok: A\n", encoding="utf-8")
        case = ah.load_adhoc_case(f)
        assert case.id == "ADHOC"
        assert [s.action for s in case.steps] == ["click", "wait_status_ok"]
        assert case.page == "/datacompare"

    def test_mapping_with_page_and_expect(self, tmp_path):
        f = tmp_path / "s.yaml"
        f.write_text(
            "page: /dataskew\n"
            "steps:\n  - click: 连接\n"
            "expect:\n  - text_contains: {in: 状态, text: 已连接}\n",
            encoding="utf-8")
        case = ah.load_adhoc_case(f)
        assert case.page == "/dataskew"
        assert case.expect[0].kind == "text_contains"

    def test_full_case_list_form(self, tmp_path):
        f = tmp_path / "s.yaml"
        f.write_text(
            "- id: T1\n  title: demo\n  page: /settings\n"
            "  steps:\n    - click: 保存\n",
            encoding="utf-8")
        case = ah.load_adhoc_case(f)
        assert case.id == "T1"
        assert case.page == "/settings"

    def test_page_override_wins(self, tmp_path):
        f = tmp_path / "s.yaml"
        f.write_text("page: /a\nsteps:\n  - click: 连接\n", encoding="utf-8")
        assert ah.load_adhoc_case(f, page="/b").page == "/b"

    def test_json_file(self, tmp_path):
        f = tmp_path / "s.json"
        f.write_text(json.dumps([{"click": "连接"}]), encoding="utf-8")
        assert ah.load_adhoc_case(f).steps[0].action == "click"

    def test_fixture_use_works(self, tmp_path):
        f = tmp_path / "s.yaml"
        f.write_text("- use: connect_a_sqlite\n", encoding="utf-8")
        case = ah.load_adhoc_case(f)
        assert len(case.steps) >= 3          # fixture spliced in

    def test_empty_file_rejected(self, tmp_path):
        f = tmp_path / "s.yaml"
        f.write_text("", encoding="utf-8")
        with pytest.raises(CaseLoadError, match="步骤"):
            ah.load_adhoc_case(f)

    def test_missing_file_rejected(self, tmp_path):
        with pytest.raises(CaseLoadError, match="不存在"):
            ah.load_adhoc_case(tmp_path / "nope.yaml")

    def test_unknown_action_rejected(self, tmp_path):
        f = tmp_path / "s.yaml"
        f.write_text("- clickk: x\n", encoding="utf-8")
        with pytest.raises(CaseLoadError, match="unknown action"):
            ah.load_adhoc_case(f)

    def test_ai_step_rejected(self, tmp_path):
        f = tmp_path / "s.yaml"
        f.write_text("- ai: 点一下连接\n", encoding="utf-8")
        with pytest.raises(CaseLoadError, match="ai"):
            ah.load_adhoc_case(f)


# ── run_adhoc orchestration (browser layer mocked) ──

class TestRunAdhoc:
    def test_runs_case_without_llm(self, tmp_path, monkeypatch):
        f = tmp_path / "s.yaml"
        f.write_text("- click: 连接\n", encoding="utf-8")

        from seatunnel_agent.agents.devops.ui_testing import env, page, runner
        monkeypatch.setattr(env, "AppUnderTest", MagicMock())
        monkeypatch.setattr(page, "DCPage", MagicMock())
        fake_res = CaseResult("ADHOC", "t", "PASS",
                              steps=[StepLog("click", True, 5)])
        run_case = MagicMock(return_value=fake_res)
        monkeypatch.setattr(runner, "run_case", run_case)
        monkeypatch.setattr(runner, "_snap",
                            MagicMock(return_value="shots/ADHOC_final.png"))
        import playwright.sync_api as pws
        monkeypatch.setattr(pws, "sync_playwright", MagicMock())

        shots = tmp_path / "out"
        res, shots_dir = ah.run_adhoc(f, screenshot_dir=shots)
        assert shots_dir == shots and shots.is_dir()
        assert res.verdict == "PASS"
        kw = run_case.call_args.kwargs
        assert kw["llm"] is None
        assert kw["shots_dir"] == shots
        # final screenshot appended as a log line
        assert res.asserts[-1].screenshot == "shots/ADHOC_final.png"


# ── CLI wiring ──

def _fake_result(verdict: str) -> CaseResult:
    return CaseResult("ADHOC", "t", verdict,
                      steps=[StepLog("click: 连接", verdict == "PASS", 5,
                                     screenshot="shots/x.png")],
                      reason="" if verdict == "PASS" else "boom")


class TestCli:
    def test_adhoc_pass_exit_zero(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            ah, "run_adhoc",
            MagicMock(return_value=(_fake_result("PASS"), tmp_path)))
        rc = main(["adhoc", "--steps", "whatever.yaml"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "PASS" in out and "x.png" in out

    def test_adhoc_fail_exit_nonzero(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            ah, "run_adhoc",
            MagicMock(return_value=(_fake_result("ERROR"), tmp_path)))
        rc = main(["adhoc", "--steps", "whatever.yaml"])
        assert rc == 1
        assert "boom" in capsys.readouterr().out

    def test_adhoc_bad_steps_exit_two(self, monkeypatch, capsys):
        monkeypatch.setattr(
            ah, "run_adhoc",
            MagicMock(side_effect=CaseLoadError("坏文件")))
        rc = main(["adhoc", "--steps", "whatever.yaml"])
        assert rc == 2
        assert "坏文件" in capsys.readouterr().out

    def test_adhoc_requires_steps(self, capsys):
        with pytest.raises(SystemExit):
            main(["adhoc"])

    def test_adhoc_args_passed_through(self, tmp_path, monkeypatch):
        m = MagicMock(return_value=(_fake_result("PASS"), tmp_path))
        monkeypatch.setattr(ah, "run_adhoc", m)
        main(["adhoc", "--steps", "s.yaml", "--url", "http://x:1",
              "--page", "/dataskew", "--screenshot-dir", "d", "--headed"])
        kw = m.call_args.kwargs
        assert kw["url"] == "http://x:1"
        assert kw["page"] == "/dataskew"
        assert kw["screenshot_dir"] == "d"
        assert kw["headed"] is True
