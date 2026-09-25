"""Run orchestration: suite -> cases -> steps -> results.

Every case starts from a fresh page load (isolation) and switches the UI to
the case's language.  Failures never abort the run: assertion misses are
FAIL, exceptions are ERROR, both get a screenshot.
"""

from __future__ import annotations

import datetime as _dt
import logging
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from .actions import run_script_step
from .env import DEFAULT_PORT, AppUnderTest
from .loader import filter_cases, load_cases
from .models import CaseResult, RunResult, TestCase
from .page import DCPage

_log = logging.getLogger(__name__)

RUNS_DIR = Path("runs")
KEEP_RUNS = 20          # prune older run dirs beyond this many


def _prune_runs(keep: int = KEEP_RUNS) -> None:
    """Delete the oldest runs/<ts>/ dirs beyond *keep*.  Best-effort."""
    if keep <= 0:
        return
    try:
        run_dirs = sorted(
            (d for d in RUNS_DIR.iterdir()
             if d.is_dir() and d.name[:2] == "20"),
            key=lambda d: d.name)
        for d in run_dirs[:-keep]:
            import shutil
            shutil.rmtree(d, ignore_errors=True)
    except OSError:
        pass


def _snap(dc: DCPage, shots_dir: Path, case_id: str, tag: str) -> str | None:
    """Screenshot into shots/; returns path relative to the run dir."""
    try:
        shots_dir.mkdir(parents=True, exist_ok=True)
        name = f"{case_id}_{tag}.png"
        dc.screenshot(str(shots_dir / name))
        return f"shots/{name}"
    except Exception:  # noqa: BLE001 — screenshots must never fail a run
        _log.warning("screenshot failed for %s", case_id, exc_info=True)
        return None


def run_case(case: TestCase, dc: DCPage, llm, shots_dir: Path,
             app_log_tail_fn=lambda: "", llm_factory=None) -> CaseResult:
    # imported lazily so --no-llm never touches LLM config
    from .agent import run_ai_step
    from .asserts import run_assert
    from .judge import run_judge

    res = CaseResult(case.id, case.title, "PASS")
    t0 = time.time()
    tokens_before = llm.tokens_used if llm else 0
    try:
        dc.goto(case.page)
        if case.lang == "zh":
            dc.set_language("中文")

        last_result_html: str | None = None
        for step in [*case.setup, *case.steps]:
            if time.time() - t0 > case.timeout_s:
                res.verdict = "ERROR"
                res.reason = f"用例超时 (> {case.timeout_s}s)"
                return res
            if step.action == "click":
                # snapshot for a later wait_result to diff against
                try:
                    last_result_html = dc.result_html()
                except Exception:  # noqa: BLE001
                    last_result_html = None
            if step.action == "wait_result" and last_result_html is not None:
                step.args["_before_html"] = last_result_html
            log = (run_ai_step(step, dc, llm) if step.ai
                   else run_script_step(step, dc))
            res.steps.append(log)
            if not log.ok:
                if "not found" in log.detail:
                    heal_llm = llm or (llm_factory() if llm_factory else None)
                    if heal_llm is not None:
                        from .diagnose import suggest_locator
                        try:
                            digest = dc.digest()
                        except Exception:  # noqa: BLE001
                            digest = ""
                        missing = (log.detail.split("not found:")[-1]
                                   .split("(side")[0].strip()[:60])
                        hint = suggest_locator(missing, digest, heal_llm)
                        if hint:
                            log.detail = f"{log.detail}  {hint}"
                res.verdict = "ERROR"
                res.reason = f"步骤失败: {log.desc} — {log.detail}"
                log.screenshot = _snap(dc, shots_dir, case.id, "step_fail")
                return res

        for a in case.expect:
            log = (run_judge(a, dc, llm) if a.kind == "ai_judge"
                   else run_assert(a, dc))
            res.asserts.append(log)
            if not log.ok:
                res.verdict = "FAIL"
                res.reason = res.reason or log.detail
                log.screenshot = _snap(dc, shots_dir, case.id, "assert_fail")
    except Exception as e:  # noqa: BLE001 — an exception is ERROR, not a crash
        res.verdict = "ERROR"
        res.reason = f"{type(e).__name__}: {str(e)[:300]}"
        _snap(dc, shots_dir, case.id, "error")
    finally:
        diag_llm = llm
        if res.verdict in ("FAIL", "ERROR") and diag_llm is None and llm_factory:
            diag_llm = llm_factory()   # lazy: script-only runs still get attribution
        if res.verdict in ("FAIL", "ERROR") and diag_llm is not None:
            from .diagnose import diagnose
            try:
                digest = dc.digest()
            except Exception:  # noqa: BLE001
                digest = ""
            attribution = diagnose(res, digest, app_log_tail_fn(), diag_llm)
            if attribution:
                res.reason = f"{res.reason}  {attribution}"
        res.elapsed_ms = int((time.time() - t0) * 1000)
        res.tokens = (llm.tokens_used - tokens_before) if llm else 0
    return res


def run_suite(
    suite: str = "smoke",
    case_ids: list[str] | None = None,
    headed: bool = False,
    port: int = DEFAULT_PORT,
    no_llm: bool = False,
    keep_app: bool = False,
    base_url: str = "",
    cases_dir: str | Path | None = None,
    on_progress=None,
) -> tuple[RunResult, Path]:
    """Run the selected cases; returns (result, run_dir)."""
    all_cases = load_cases(cases_dir) if cases_dir else load_cases()
    cases = filter_cases(all_cases, suite, case_ids)
    manual = [c for c in all_cases if "manual" in c.tags] if not case_ids else []

    _prune_runs()
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / ts
    shots_dir = run_dir / "shots"
    run_dir.mkdir(parents=True, exist_ok=True)

    llm = None
    if not no_llm and _needs_llm(cases):
        from .agent import UITestLLM
        llm = UITestLLM()

    _lazy: dict = {}

    def _llm_factory():
        """Diagnosis-only LLM for script-only runs; never breaks the run
        (missing API key etc. just means no attribution)."""
        if no_llm:
            return None
        if "llm" not in _lazy:
            try:
                from .agent import UITestLLM
                _lazy["llm"] = UITestLLM()
            except Exception:  # noqa: BLE001
                _lazy["llm"] = None
        return _lazy["llm"]

    rr = RunResult(started_at=ts, suite=suite if not case_ids else
                   ",".join(case_ids))
    t0 = time.time()

    with AppUnderTest(port=port, log_dir=run_dir, keep_app=keep_app,
                      external_url=base_url) as app:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not headed)
            page = browser.new_page(viewport={"width": 1600, "height": 900})
            page.set_default_timeout(10_000)
            dc = DCPage(page, app.base_url)

            for i, case in enumerate(cases, 1):
                if _skip_reason(case, no_llm):
                    cr = CaseResult(case.id, case.title, "SKIP",
                                    reason=_skip_reason(case, no_llm))
                else:
                    cr = run_case(case, dc, llm, shots_dir,
                                  app_log_tail_fn=app.log_tail,
                                  llm_factory=_llm_factory)
                rr.cases.append(cr)
                if on_progress:
                    on_progress(i, len(cases), cr)

            browser.close()
        rr.app_log_tail = app.log_tail()

    for c in manual:
        rr.cases.append(CaseResult(c.id, c.title, "MANUAL",
                                   reason="标注为人工用例"))

    rr.elapsed_ms = int((time.time() - t0) * 1000)
    diag = _lazy.get("llm")
    rr.tokens = (llm.tokens_used if llm else 0) + (diag.tokens_used if diag else 0)
    return rr, run_dir


def _needs_llm(cases: list[TestCase]) -> bool:
    for c in cases:
        if any(s.ai for s in [*c.setup, *c.steps]):
            return True
        if any(a.kind == "ai_judge" for a in c.expect):
            return True
    return False


def _skip_reason(case: TestCase, no_llm: bool) -> str:
    if "hive" in case.tags:
        import os
        if not os.getenv("HIVE_HOST"):
            return "需要真实 Hive (.env 未配置 HIVE_HOST)"
    if no_llm:
        has_ai = (any(s.ai for s in [*case.setup, *case.steps])
                  or any(a.kind == "ai_judge" for a in case.expect))
        if has_ai:
            return "--no-llm 模式跳过含 ai 步骤/断言的用例"
    return ""
