# -*- coding: utf-8 -*-
"""Unit tests for the UI testing agent framework (no browser, no tokens)."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from seatunnel_agent.ui_testing import loader as ldr
from seatunnel_agent.ui_testing.asserts import run_assert
from seatunnel_agent.ui_testing.loader import (
    CaseLoadError,
    filter_cases,
    load_cases,
)
from seatunnel_agent.ui_testing.models import Assertion, Step
from seatunnel_agent.ui_testing.seed_sqlite import SEED, seed_sqlite


# ── loader ──

class TestLoader:
    def test_builtin_cases_load(self):
        cases = load_cases()
        assert len(cases) >= 55
        ids = [c.id for c in cases]
        assert len(ids) == len(set(ids)), "case ids must be unique"

    def test_smoke_suite_size(self):
        cases = filter_cases(load_cases(), "smoke")
        assert len(cases) >= 20

    def test_shorthand_click(self):
        steps = ldr._expand_step({"click": "连接"}, {}, "t")
        assert steps[0].action == "click"
        assert steps[0].args == {"target": "连接"}

    def test_fill_expands_per_label(self):
        steps = ldr._expand_step(
            {"fill": {"主机": "1.2.3.4", "端口": "10000", "side": "B"}}, {}, "t")
        assert len(steps) == 2
        assert all(s.action == "fill" for s in steps)
        assert steps[0].args["side"] == "B"
        assert steps[1].args["side"] == "B"

    def test_fixture_use_splices(self):
        fixtures = {"conn": [{"click": "连接"}, {"wait_status_ok": "A"}]}
        steps = ldr._expand_step({"use": "conn"}, fixtures, "t")
        assert [s.action for s in steps] == ["click", "wait_status_ok"]

    def test_unknown_action_rejected(self):
        with pytest.raises(CaseLoadError, match="unknown action"):
            ldr._expand_step({"clickk": "x"}, {}, "t")

    def test_unknown_fixture_rejected(self):
        with pytest.raises(CaseLoadError, match="unknown fixture"):
            ldr._expand_step({"use": "nope"}, {}, "t")

    def test_bare_wait_requires_note(self):
        with pytest.raises(CaseLoadError, match="note"):
            ldr._expand_step({"wait": 500}, {}, "t")
        steps = ldr._expand_step({"wait": 500, "note": "why"}, {}, "t")
        assert steps[0].args == {"ms": 500}

    def test_inline_password_rejected(self):
        with pytest.raises(CaseLoadError, match="credential"):
            ldr._expand_step({"fill": {"密码": "hunter2"}}, {}, "t")

    def test_yaml_on_key_normalized(self):
        # YAML 1.1: a bare `on:` key parses as boolean True
        import yaml
        raw = yaml.safe_load("check: {target: 启用脱敏, on: false}")
        steps = ldr._expand_step(raw, {}, "t")
        assert steps[0].args["on"] is False

    def test_ai_step(self):
        steps = ldr._expand_step({"ai": "打开下拉框"}, {}, "t")
        assert steps[0].ai == "打开下拉框"
        assert steps[0].action is None

    def test_assert_shorthand(self):
        a = ldr._expand_assert({"status_error": {"side": "A"}}, "t")
        assert a.kind == "status_error" and a.args["side"] == "A"
        j = ldr._expand_assert({"ai_judge": "高亮"}, "t")
        assert j.kind == "ai_judge" and j.args["expect"] == "高亮"

    def test_unknown_assert_rejected(self):
        with pytest.raises(CaseLoadError, match="unknown assertion"):
            ldr._expand_assert({"text_containz": {"text": "x"}}, "t")

    def test_filter_by_case_id(self):
        cases = load_cases()
        picked = filter_cases(cases, "", ["a4", "B3"])
        assert {c.id for c in picked} == {"A4", "B3"}

    def test_filter_unknown_id_raises(self):
        with pytest.raises(CaseLoadError, match="unknown case id"):
            filter_cases(load_cases(), "", ["ZZ99"])

    def test_full_excludes_hive_slow_manual(self):
        full = filter_cases(load_cases(), "full")
        for c in full:
            assert "manual" not in c.tags
            assert "hive" not in c.tags
            assert "slow" not in c.tags


# ── seed data stays in sync with the Hive SQL file ──

class TestSeedSqlite:
    def test_seed_creates_ten_tables(self, tmp_path):
        db = tmp_path / "t.db"
        seed_sqlite(db)
        conn = sqlite3.connect(db)
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert len([n for n in names if n.startswith("dc_test_")]) == 10

    def test_seed_is_idempotent(self, tmp_path):
        db = tmp_path / "t.db"
        seed_sqlite(db)
        seed_sqlite(db)
        conn = sqlite3.connect(db)
        n = conn.execute("SELECT COUNT(*) FROM dc_test_orders_a").fetchone()[0]
        conn.close()
        assert n == 10

    def test_expected_row_counts(self, tmp_path):
        db = tmp_path / "t.db"
        seed_sqlite(db)
        conn = sqlite3.connect(db)
        expect = {"dc_test_orders_a": 10, "dc_test_orders_b": 9,
                  "dc_test_schema_a": 3, "dc_test_schema_b": 3,
                  "dc_test_metrics_a": 20, "dc_test_metrics_b": 20,
                  "dc_test_part_a": 15, "dc_test_part_b": 8,
                  "dc_test_same_a": 5, "dc_test_same_b": 5}
        for table, n in expect.items():
            got = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert got == n, table
        conn.close()

    def test_rows_match_hive_sql_file(self):
        """Single source of truth: the Python constants must equal the row
        data in examples/dc_hive_test_data.sql."""
        sql_path = Path(__file__).parent.parent / "examples" / "dc_hive_test_data.sql"
        if not sql_path.is_file():
            pytest.skip("dc_hive_test_data.sql not present")
        text = sql_path.read_text(encoding="utf-8")

        sql_rows: dict[str, list[tuple]] = {}
        # plain INSERT INTO <t> VALUES (...);  and partitioned inserts
        for m in re.finditer(
                r"INSERT INTO (dc_test_\w+)(?:\s+PARTITION \(dt='([^']+)'\))?"
                r"\s+VALUES\s*(.*?);", text, re.DOTALL):
            table, dt, body = m.group(1), m.group(2), m.group(3)
            rows = sql_rows.setdefault(table, [])
            for rm in re.finditer(r"\(([^()]*)\)", body):
                vals = []
                for tok in re.findall(r"'[^']*'|[^,]+", rm.group(1)):
                    tok = tok.strip()
                    if not tok:
                        continue
                    if tok.upper() == "NULL":
                        vals.append(None)
                    elif tok.startswith("'"):
                        vals.append(tok.strip("'"))
                    else:
                        vals.append(float(tok) if "." in tok else int(tok))
                if dt:
                    vals.append(dt)
                rows.append(tuple(vals))

        seed_map = {t: rows for t, _, rows in SEED}
        assert set(seed_map) == set(sql_rows)
        for table in seed_map:
            assert seed_map[table] == sql_rows[table], (
                f"{table} drifted between seed_sqlite.py and the SQL file")


# ── deterministic asserts against a mock DCPage ──

def _mock_dc(**kw) -> MagicMock:
    dc = MagicMock()
    dc.status_text.return_value = kw.get("status", "")
    dc.result_text.return_value = kw.get("result", "")
    dc.dropdown_options.return_value = kw.get("options", [])
    dc.is_visible.return_value = kw.get("visible", True)
    box = MagicMock()
    box.input_value.return_value = kw.get("value", "")
    dc.textbox.return_value = box
    return dc


class TestAsserts:
    def test_text_contains_pass_and_fail(self):
        dc = _mock_dc(result="Count (A): 10 | Count (B): 9")
        ok = run_assert(Assertion("text_contains",
                                  {"in": "结果区", "text": "10"}), dc)
        assert ok.ok
        bad = run_assert(Assertion("text_contains",
                                   {"in": "结果区", "text": "42"}), dc)
        assert not bad.ok
        assert "Count (A)" in bad.detail, "failure must show the actual value"

    def test_status_marks(self):
        dc = _mock_dc(status="✅ connected")
        assert run_assert(Assertion("status_ok", {"side": "A"}), dc).ok
        assert not run_assert(Assertion("status_error", {"side": "A"}), dc).ok

    def test_value_is(self):
        dc = _mock_dc(value="10.0.0.1")
        good = run_assert(Assertion(
            "value_is", {"of": "主机", "side": "A", "value": "10.0.0.1"}), dc)
        assert good.ok
        bad = run_assert(Assertion(
            "value_is", {"of": "主机", "side": "A", "value": "x"}), dc)
        assert not bad.ok and "10.0.0.1" in bad.detail

    def test_options_count_and_are(self):
        dc = _mock_dc(options=["a", "b"])
        assert run_assert(Assertion("options_count",
                                    {"of": "选择表", "n": 2}), dc).ok
        assert run_assert(Assertion("options_are",
                                    {"of": "选择表", "values": ["b", "a"]}), dc).ok
        bad = run_assert(Assertion("options_count",
                                   {"of": "选择表", "n": 3}), dc)
        assert not bad.ok and "actual 2" in bad.detail

    def test_hidden(self):
        dc = _mock_dc(visible=False)
        assert run_assert(Assertion("hidden", {"target": "主机"}), dc).ok
        assert not run_assert(Assertion("visible", {"target": "主机"}), dc).ok

    def test_exception_becomes_fail(self):
        dc = MagicMock()
        dc.status_text.side_effect = RuntimeError("boom")
        log = run_assert(Assertion("status_ok", {"side": "A"}), dc)
        assert not log.ok and "boom" in log.detail


# ── LLM agent loop with a mocked client (no tokens spent) ──

class TestAgentLoop:
    def _llm(self, responses):
        """A UITestLLM whose client replays the given LLMResponses."""
        from seatunnel_agent.ui_testing.agent import UITestLLM
        llm = UITestLLM.__new__(UITestLLM)
        llm.tokens_used = 0
        client = MagicMock()
        client.chat.side_effect = responses
        client.append_assistant.side_effect = lambda rc: {
            "role": "assistant", "content": rc}
        client.build_tool_result_message.side_effect = lambda trs: {
            "role": "user", "content": trs}
        llm.client = client
        return llm

    @staticmethod
    def _resp(tool_calls=None, text="", usage=None):
        r = MagicMock()
        r.wants_tool_use = bool(tool_calls)
        r.tool_calls = tool_calls or []
        r.reply_text = text
        r.raw_content = []
        r.usage = usage or {"input_tokens": 100, "output_tokens": 50}
        return r

    @staticmethod
    def _tc(name, inp):
        tc = MagicMock()
        tc.name, tc.input, tc.id = name, inp, "t1"
        return tc

    def test_done_success(self):
        from seatunnel_agent.ui_testing.agent import run_ai_step
        llm = self._llm([
            self._resp([self._tc("click", {"target": "连接"})]),
            self._resp([self._tc("done", {"success": True})]),
        ])
        dc = MagicMock()
        dc.digest.return_value = "[PAGE]"
        log = run_ai_step(Step(ai="点连接"), dc, llm)
        assert log.ok
        dc.click_button.assert_called_once_with("连接", None)

    def test_done_failure_reason(self):
        from seatunnel_agent.ui_testing.agent import run_ai_step
        llm = self._llm([
            self._resp([self._tc("done", {"success": False,
                                          "reason": "找不到按钮"})]),
        ])
        dc = MagicMock()
        dc.digest.return_value = "[PAGE]"
        log = run_ai_step(Step(ai="点一个不存在的按钮"), dc, llm)
        assert not log.ok and "找不到按钮" in log.detail

    def test_round_cap(self):
        from seatunnel_agent.ui_testing.agent import MAX_ROUNDS, run_ai_step
        llm = self._llm([
            self._resp([self._tc("read_page", {})])] * (MAX_ROUNDS + 1))
        dc = MagicMock()
        dc.digest.return_value = "[PAGE]"
        log = run_ai_step(Step(ai="转圈"), dc, llm)
        assert not log.ok and str(MAX_ROUNDS) in log.detail

    def test_token_budget_cap(self):
        from seatunnel_agent.ui_testing.agent import run_ai_step
        big = {"input_tokens": 40_000, "output_tokens": 1}
        llm = self._llm([self._resp([self._tc("read_page", {})], usage=big)])
        dc = MagicMock()
        dc.digest.return_value = "[PAGE]"
        log = run_ai_step(Step(ai="烧钱"), dc, llm)
        assert not log.ok and "预算" in log.detail

    def test_no_tool_use_fails(self):
        from seatunnel_agent.ui_testing.agent import run_ai_step
        llm = self._llm([self._resp(text="我觉得应该点连接")])
        dc = MagicMock()
        dc.digest.return_value = "[PAGE]"
        log = run_ai_step(Step(ai="点连接"), dc, llm)
        assert not log.ok and "未调用工具" in log.detail

    def test_tool_error_fed_back(self):
        from seatunnel_agent.ui_testing.agent import _exec_tool
        dc = MagicMock()
        dc.click_button.side_effect = LookupError("button not found: x")
        out = _exec_tool("click", {"target": "x"}, dc)
        assert out.startswith("ERROR:") and "button not found" in out


# ── checklist coverage ──

class TestCoverage:
    def test_counts_and_statuses(self):
        from seatunnel_agent.ui_testing.coverage import compute_coverage
        cov = compute_coverage(load_cases())
        if cov is None:
            pytest.skip("checklist html not present")
        counts = cov.counts()
        assert len(cov.rows) == 75
        assert counts["runner"] == 3            # P0-1/2/3
        assert counts["auto"] >= 55             # PRD acceptance threshold
        assert counts["missing"] <= 8
        # beyond-checklist extras never collide with checklist ids
        checklist_ids = {r.item_id.upper() for r in cov.rows}
        assert not (set(x.upper() for x in cov.extra_case_ids) & checklist_ids)
        assert "SR1" in cov.extra_case_ids       # sanity: SR group is extra

    def test_absent_checklist_returns_none(self, tmp_path):
        from seatunnel_agent.ui_testing.coverage import compute_coverage
        assert compute_coverage(load_cases(), path=tmp_path / "nope.html") is None


# ── judge parsing ──

class TestJudge:
    def test_parse_verdicts(self):
        from seatunnel_agent.ui_testing.judge import _parse
        assert _parse('{"verdict": "pass", "reason": "ok"}')["verdict"] == "pass"
        assert _parse('前缀 {"verdict": "fail", "reason": "差"} 后缀')["verdict"] == "fail"
        assert _parse("not json") is None
        assert _parse('{"verdict": "maybe"}') is None

    def test_adversarial_verdict_fail(self, monkeypatch):
        """verdict: fail — a false expectation must be judged fail."""
        import json as _json

        from seatunnel_agent.ui_testing import judge as judge_mod
        from seatunnel_agent.ui_testing.models import Assertion

        monkeypatch.setattr(judge_mod, "_judge_cache", {})
        monkeypatch.setenv("UITEST_JUDGE_VISION", "0")

        def _llm(judge_verdict):
            resp = MagicMock()
            resp.reply_text = _json.dumps(
                {"verdict": judge_verdict, "reason": "r"})
            resp.usage = {"input": 1, "output": 1}
            llm = MagicMock()
            llm.client.provider = "anthropic"
            llm.client.chat.return_value = resp
            return llm

        class _DC:
            def digest(self, max_result_chars=2500):
                return "same summary"

        a = Assertion(kind="ai_judge",
                      args={"expect": "行数完全一致", "verdict": "fail"})
        # judge correctly rejects the false claim -> assertion passes
        ok_log = judge_mod.run_judge(a, _DC(), _llm("fail"))
        assert ok_log.ok and "期望判 fail" in ok_log.desc
        # judge rubber-stamps -> assertion fails loudly
        monkeypatch.setattr(judge_mod, "_judge_cache", {})
        bad_log = judge_mod.run_judge(a, _DC(), _llm("pass"))
        assert not bad_log.ok
        assert "幻觉盖章" in bad_log.detail

    def test_cache_key_includes_wanted_verdict(self, monkeypatch):
        """Same expect+digest with opposite wanted verdicts must not share
        a cache entry."""
        import json as _json

        from seatunnel_agent.ui_testing import judge as judge_mod
        from seatunnel_agent.ui_testing.models import Assertion

        monkeypatch.setattr(judge_mod, "_judge_cache", {})
        monkeypatch.setenv("UITEST_JUDGE_VISION", "0")
        resp = MagicMock()
        resp.reply_text = _json.dumps({"verdict": "pass", "reason": "r"})
        resp.usage = {"input": 1, "output": 1}
        llm = MagicMock()
        llm.client.provider = "anthropic"
        llm.client.chat.return_value = resp

        class _DC:
            def digest(self, max_result_chars=2500):
                return "same summary"

        pos = Assertion(kind="ai_judge", args={"expect": "X"})
        neg = Assertion(kind="ai_judge", args={"expect": "X",
                                               "verdict": "fail"})
        assert judge_mod.run_judge(pos, _DC(), llm).ok          # pass wanted
        neg_log = judge_mod.run_judge(neg, _DC(), llm)
        assert not neg_log.ok                                   # fresh judge
        assert "(cached)" not in neg_log.detail

    def test_loader_rejects_bad_verdict(self):
        from seatunnel_agent.ui_testing.loader import validate_case_yaml
        bad = """
- id: NEGX
  title: bad verdict
  tags: [full, sqlite]
  steps: [{wait: 100, note: n}]
  expect:
    - ai_judge: {expect: x, verdict: maybe}
"""
        with pytest.raises(CaseLoadError):
            validate_case_yaml(bad)

    def test_cache_skips_second_llm_call(self, monkeypatch):
        from seatunnel_agent.ui_testing import judge as judge_mod
        from seatunnel_agent.ui_testing.models import Assertion

        monkeypatch.setattr(judge_mod, "_judge_cache", {})
        monkeypatch.setenv("UITEST_JUDGE_VISION", "0")
        calls = {"n": 0}

        class _Resp:
            reply_text = '{"verdict": "pass", "reason": "ok"}'
            usage = {"input": 1, "output": 1}

        class _Client:
            provider = "anthropic"
            def chat(self, *a, **k):
                calls["n"] += 1
                return _Resp()

        class _LLM:
            client = _Client()
            def spend(self, usage):
                pass

        class _DC:
            def digest(self, max_result_chars=2500):
                return "same summary"

        a = Assertion(kind="ai_judge", args={"expect": "结果高亮"})
        log1 = judge_mod.run_judge(a, _DC(), _LLM())
        log2 = judge_mod.run_judge(a, _DC(), _LLM())
        assert log1.ok and log2.ok
        assert calls["n"] == 1                    # second verdict from cache
        assert "(cached)" in log2.detail


# ── locator self-healing loop ──

class TestSelfHeal:
    """The page's button was renamed to 'New Label'; cases still say 旧按钮."""

    def _reset(self):
        from seatunnel_agent.ui_testing import page as page_mod
        from seatunnel_agent.ui_testing import runner
        page_mod.reset_aliases()
        runner._heal_failed.clear()

    def _dc(self):
        from seatunnel_agent.ui_testing import page as page_mod

        class DC:
            page = MagicMock()

            def goto(self, p):
                pass

            def set_language(self, lang):
                pass

            def digest(self, **k):
                return "[BUTTONS] New Label 保存"

            def result_html(self):
                return ""

            def screenshot(self, p):
                pass

            def click_button(self, name, side=None):
                for text in page_mod._texts(name):
                    if text == "New Label":
                        return
                raise LookupError(f"button not found: {name} (side={side})")

        return DC()

    def _llm(self, label="New Label"):
        import json as _json

        from seatunnel_agent.ui_testing.agent import UITestLLM
        llm = UITestLLM.__new__(UITestLLM)
        llm.tokens_used = 0
        resp = MagicMock()
        resp.reply_text = _json.dumps(
            {"found": True, "label": label, "hint": "renamed"})
        resp.usage = {"input": 1, "output": 1}
        llm.client = MagicMock()
        llm.client.chat.return_value = resp
        return llm

    def _case(self):
        from seatunnel_agent.ui_testing.models import TestCase
        return TestCase(id="H1", title="heal demo", tags=["sqlite"],
                        page="/x",
                        steps=[Step(action="click", args={"target": "旧按钮"})])

    def test_heal_success_then_alias_reused(self, tmp_path):
        from seatunnel_agent.ui_testing import page as page_mod
        from seatunnel_agent.ui_testing.runner import run_case
        self._reset()
        dc, llm = self._dc(), self._llm()

        cr = run_case(self._case(), dc, llm, tmp_path)
        assert cr.verdict == "HEALED"
        assert cr.healed == ["旧按钮 -> New Label"]
        assert page_mod.healed_aliases() == {"旧按钮": ["New Label"]}
        heal_calls = llm.client.chat.call_count

        # second case resolves straight through the alias: no failure, no LLM
        cr2 = run_case(self._case(), dc, llm, tmp_path)
        assert cr2.verdict == "PASS"
        assert llm.client.chat.call_count == heal_calls
        self._reset()

    def test_bad_suggestion_rolls_back(self, tmp_path, monkeypatch):
        from seatunnel_agent.ui_testing import page as page_mod
        from seatunnel_agent.ui_testing import runner
        self._reset()
        dc = self._dc()
        # '保存' IS on the page (passes the digest gate) but is not the
        # renamed control — the verified retry must fail and roll back
        llm = self._llm(label="保存")

        cr = runner.run_case(self._case(), dc, llm, tmp_path)
        assert cr.verdict == "ERROR"
        assert "自愈失败" in cr.reason
        assert page_mod.healed_aliases() == {}          # rolled back
        assert "旧按钮" in runner._heal_failed           # negative cache

        # later case: fails fast, no second suggestion round
        calls = {"n": 0}
        monkeypatch.setattr(
            "seatunnel_agent.ui_testing.diagnose.suggest_locator_struct",
            lambda *a, **k: calls.__setitem__("n", calls["n"] + 1))
        cr2 = runner.run_case(self._case(), dc, llm, tmp_path)
        assert cr2.verdict == "ERROR"
        assert calls["n"] == 0
        self._reset()

    def test_digest_gate_blocks_hallucination(self):
        from seatunnel_agent.ui_testing.diagnose import suggest_locator_struct
        llm = self._llm(label="Ghost Button")   # not in the digest below
        assert suggest_locator_struct("旧按钮", "[BUTTONS] New Label", llm) is None

    def test_labels_patch_lines(self):
        from seatunnel_agent.ui_testing.models import CaseResult, RunResult
        from seatunnel_agent.ui_testing.report import _labels_patch_lines
        rr = RunResult(started_at="t", suite="smoke", cases=[
            CaseResult("H1", "t", "HEALED", healed=["连接 -> Connect Now"]),
        ])
        (line,) = _labels_patch_lines(rr)
        assert '"连接": ("连接", "Connect", "Connect Now")' in line
        assert "healed: H1" in line

    def test_labels_patch_escapes_quotes(self):
        from seatunnel_agent.ui_testing.models import CaseResult, RunResult
        from seatunnel_agent.ui_testing.report import _labels_patch_lines
        rr = RunResult(started_at="t", suite="smoke", cases=[
            CaseResult("H1", "t", "HEALED", healed=['连接 -> Say "Hi"']),
        ])
        (line,) = _labels_patch_lines(rr)
        assert '"Say \\"Hi\\""' in line          # valid python when pasted

    def test_assert_side_healing(self, tmp_path):
        from seatunnel_agent.ui_testing import page as page_mod
        from seatunnel_agent.ui_testing.models import Assertion, TestCase
        from seatunnel_agent.ui_testing.runner import run_case
        self._reset()
        llm = self._llm()

        class DC:
            page = MagicMock()

            def goto(self, p):
                pass

            def set_language(self, lang):
                pass

            def digest(self, **k):
                return "[INPUTS] New Label"

            def screenshot(self, p):
                pass

            def textbox(self, name, side=None):
                for text in page_mod._texts(name):
                    if text == "New Label":
                        box = MagicMock()
                        box.input_value.return_value = "v"
                        return box
                raise LookupError(f"textbox not found: {name} (side={side})")

            def dropdown_input(self, name, side=None):
                # value_is falls back here after the textbox LookupError,
                # exactly like the real DCPage
                raise LookupError(f"dropdown not found: {name} (side={side})")

        case = TestCase(id="H2", title="assert heal", tags=["sqlite"],
                        page="/x", steps=[],
                        expect=[Assertion(kind="value_is",
                                          args={"of": "旧框", "value": "v"})])
        cr = run_case(case, DC(), llm, tmp_path)
        assert cr.verdict == "HEALED"
        assert cr.healed == ["旧框 -> New Label"]
        self._reset()

    def test_healed_counts_and_flaky_normalization(self):
        from seatunnel_agent.ui_testing.models import CaseResult, RunResult
        from seatunnel_agent.ui_testing.rundiff import CaseDelta, flaky_trend
        rr = RunResult(started_at="t", suite="smoke", cases=[
            CaseResult("H1", "t", "HEALED")])
        assert rr.counts()["HEALED"] == 1
        # HEALED -> PASS across rounds is the healing working, not flaky
        rows = flaky_trend([
            {"ts": "1", "verdicts": {"H1": "HEALED"}},
            {"ts": "2", "verdicts": {"H1": "PASS"}},
        ])
        assert rows[0]["flaky"] is False
        # a healed case that later hard-fails is a regression
        assert CaseDelta("H1", "t", old="HEALED", new="FAIL",
                         old_ms=0, new_ms=0).regressed


# ── report masking ──

class TestReportMask:
    def test_mask_replaces_secrets(self, monkeypatch):
        from seatunnel_agent.ui_testing import report
        monkeypatch.setenv("HIVE_PASSWORD", "supersecret99")
        assert "supersecret99" not in report.mask("pw is supersecret99!")


class TestFlakyTrend:
    def _hist(self, tmp_path, rows):
        import json
        (tmp_path / "history.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    def test_history_roundtrip_and_trend(self, tmp_path):
        from seatunnel_agent.ui_testing.models import CaseResult, RunResult
        from seatunnel_agent.ui_testing.report import append_history
        from seatunnel_agent.ui_testing.rundiff import (
            flaky_trend, load_history)
        rr = RunResult(started_at="20260101_000000", suite="smoke")
        rr.cases = [CaseResult("A1", "t", "PASS"),
                    CaseResult("B1", "t", "FAIL"),
                    CaseResult("L6", "t", "SKIP")]
        append_history(rr, tmp_path)
        rr2 = RunResult(started_at="20260101_010000", suite="smoke")
        rr2.cases = [CaseResult("A1", "t", "PASS"),
                     CaseResult("B1", "t", "PASS")]
        append_history(rr2, tmp_path)
        records = load_history(tmp_path)
        assert len(records) == 2
        rows = {r["case_id"]: r for r in flaky_trend(records)}
        assert rows["B1"]["flaky"] and rows["B1"]["fails"] == 1
        assert not rows["A1"]["flaky"] and rows["A1"]["fail_rate"] == 0
        assert "L6" not in rows            # SKIP is not signal

    def test_trend_ignores_corrupt_lines_and_last_window(self, tmp_path):
        from seatunnel_agent.ui_testing.rundiff import load_history
        self._hist(tmp_path, [
            {"ts": "1", "suite": "s", "verdicts": {"A1": "PASS"}},
            {"ts": "2", "suite": "s", "verdicts": {"A1": "FAIL"}},
        ])
        with (tmp_path / "history.jsonl").open("a", encoding="utf-8") as fh:
            fh.write("\nnot json\n")
        assert len(load_history(tmp_path)) == 2
        assert len(load_history(tmp_path, last=1)) == 1

    def test_format_trend_marks_flaky(self, tmp_path):
        from seatunnel_agent.ui_testing.rundiff import (
            flaky_trend, format_trend, load_history)
        self._hist(tmp_path, [
            {"ts": "1", "suite": "s", "verdicts": {"A1": "PASS", "B1": "PASS"}},
            {"ts": "2", "suite": "s", "verdicts": {"A1": "ERROR", "B1": "PASS"}},
        ])
        out = format_trend(flaky_trend(load_history(tmp_path)), 2)
        assert "FLAKY" in out and "A1" in out
        assert "稳定 1 / 覆盖 2" in out
