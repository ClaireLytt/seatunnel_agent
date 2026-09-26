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


# Elements a heal attempt already failed for in this run: later cases fail
# fast instead of re-billing the LLM for the same truly-missing element.
_heal_failed: set[str] = set()


def _parse_missing(detail: str) -> str:
    """Extract the element name from a '... not found: X (side=..)' detail."""
    return detail.split("not found:")[-1].split("(side")[0].strip()[:60]


def _safe_digest(dc: DCPage) -> str:
    try:
        return dc.digest()
    except Exception:  # noqa: BLE001 — healing must never crash a run
        return ""


def _attempt_heal(missing: str, dc: DCPage, heal_llm, rerun):
    """One verified retry under an LLM-suggested alias.

    Returns ``(retry_log, "missing -> label")`` when the re-run succeeded, or
    ``(None, detail_suffix)`` when it did not — the alias is then rolled back
    and the element negative-cached for the rest of the run."""
    from .diagnose import suggest_locator_struct
    from .page import register_alias, unregister_alias
    sug = suggest_locator_struct(missing, _safe_digest(dc), heal_llm)
    if sug is None:
        _heal_failed.add(missing)
        return None, ""
    label, hint = sug
    register_alias(missing, label)
    retry = rerun()
    if retry.ok:
        retry.detail = f"🩹 HEALED: {missing!r} -> {label!r} · {retry.detail}"
        return retry, f"{missing} -> {label}"
    unregister_alias(missing, label)
    _heal_failed.add(missing)
    return None, f"  [自愈失败] 按建议 {label!r} 重试仍失败 — {hint}"


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
        # Enforce the case's language every time: the preference lives in
        # localStorage now and would otherwise leak from the previous case.
        dc.set_language("中文" if case.lang == "zh" else "English")

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
            if step.action == "screenshot":
                # route manual screenshots into this run's shots/ (they used
                # to land in the CWD because nothing injected _shots_dir)
                step.args["_shots_dir"] = str(shots_dir)
            log = (run_ai_step(step, dc, llm) if step.ai
                   else run_script_step(step, dc))
            res.steps.append(log)
            if not log.ok:
                # ── self-healing loop: a missing element gets ONE verified
                # retry under an LLM-suggested alias. A wrong suggestion just
                # fails the retry and is rolled back — the LLM nominates, the
                # deterministic re-run decides. Verified aliases live in
                # page.RUNTIME_ALIASES so every later case resolves directly.
                if "not found" in log.detail:
                    heal_llm = llm or (llm_factory() if llm_factory else None)
                    missing = _parse_missing(log.detail)
                    if heal_llm is not None and missing:
                        if step.ai:
                            # the agent loop self-corrects by observation;
                            # a lookup it gave up on only gets a report hint
                            from .diagnose import suggest_locator
                            hint = suggest_locator(
                                missing, _safe_digest(dc), heal_llm)
                            if hint:
                                log.detail += f"  {hint}"
                        elif missing not in _heal_failed:
                            retry, extra = _attempt_heal(
                                missing, dc, heal_llm,
                                lambda: run_script_step(step, dc))
                            if retry is not None:
                                res.steps.append(retry)
                                if extra not in res.healed:
                                    res.healed.append(extra)
                                continue          # case goes on, no ERROR
                            log.detail += extra
                res.verdict = "ERROR"
                res.reason = f"步骤失败: {log.desc} — {log.detail}"
                log.screenshot = _snap(dc, shots_dir, case.id, "step_fail")
                return res

        for a in case.expect:
            log = (run_judge(a, dc, llm) if a.kind == "ai_judge"
                   else run_assert(a, dc))
            # assert-side healing: a control referenced only in `expect`
            # (visible / value_is / text_contains-in-label) heals the same
            # way — nominate, alias, re-run the assertion to verify.
            if not log.ok and a.kind != "ai_judge" and "not found" in log.detail:
                heal_llm = llm or (llm_factory() if llm_factory else None)
                missing = _parse_missing(log.detail)
                if (heal_llm is not None and missing
                        and missing not in _heal_failed):
                    retry, extra = _attempt_heal(
                        missing, dc, heal_llm,
                        lambda a=a: run_assert(a, dc))
                    if retry is not None:
                        res.asserts.append(log)
                        res.asserts.append(retry)
                        if extra not in res.healed:
                            res.healed.append(extra)
                        continue
                    log.detail += extra
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
        # only a fully green case counts as healed — a later FAIL stays FAIL
        if res.verdict == "PASS" and res.healed:
            res.verdict = "HEALED"
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

    # fresh healing state per run
    from .page import reset_aliases
    reset_aliases()
    _heal_failed.clear()

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
