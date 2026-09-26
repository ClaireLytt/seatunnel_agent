"""Deterministic assertion engine.

Every failure message contains the *actual* value so a red report line is
diagnosable without re-running.
"""

from __future__ import annotations

import time

from .models import Assertion, StepLog
from .page import DCPage


def _ms(t0: float) -> int:
    return int((time.time() - t0) * 1000)


def run_assert(a: Assertion, dc: DCPage) -> StepLog:
    t0 = time.time()
    try:
        ok, detail = _check(a, dc)
        return StepLog(a.desc, ok, _ms(t0), detail)
    except Exception as e:  # noqa: BLE001 — assertion errors become FAIL logs
        return StepLog(a.desc, False, _ms(t0),
                       f"{type(e).__name__}: {e}")


def _read_text(dc: DCPage, where: str, side: str | None) -> str:
    """'状态' reads the status textbox; '结果区' reads the result area;
    anything else is treated as a textbox label."""
    if where in ("状态", "Status", "status"):
        return dc.status_text(side or "A")
    if where in ("结果区", "结果", "result", "Result"):
        return dc.result_text()
    if where in ("页面", "page", "body"):
        return dc.page.locator("body").inner_text()
    return dc.textbox(where, side).input_value()


def _check(a: Assertion, dc: DCPage) -> tuple[bool, str]:
    k, args = a.kind, a.args
    side = args.get("side")

    if k in ("text_contains", "text_not_contains"):
        where = args.get("in", "结果区")
        needle = str(args.get("text", args.get("target", "")))
        actual = _read_text(dc, where, side)
        found = needle.casefold() in actual.casefold()
        ok = found if k == "text_contains" else not found
        want = "contain" if k == "text_contains" else "NOT contain"
        snippet = actual if len(actual) <= 300 else actual[:300] + "…"
        return ok, (f"'{where}' does{'' if found else ' not'} contain "
                    f"{needle!r} (expected to {want}); actual={snippet!r}")

    if k in ("value_is", "value_contains"):
        name = args.get("of", args.get("target"))
        want = str(args.get("value", ""))
        try:
            actual = dc.textbox(name, side).input_value()
        except LookupError:
            actual = dc.dropdown_input(name, side).input_value()
        ok = (want in actual) if k == "value_contains" else (actual == want)
        rel = "to contain" if k == "value_contains" else "to equal"
        return ok, f"'{name}' value: expected {rel} {want!r}, actual {actual!r}"

    if k in ("options_are", "options_count"):
        name = args.get("of", "选择表")
        keep = bool(args.get("keep_filter", False))
        opts = dc.dropdown_options(name, side, keep_filter=keep)
        if k == "options_count":
            n = int(args.get("n", args.get("count", 0)))
            return len(opts) == n, (f"'{name}' options: expected {n}, "
                                    f"actual {len(opts)}: {opts}")
        want = [str(v) for v in args.get("values", [])]
        return sorted(opts) == sorted(want), (
            f"'{name}' options: expected {sorted(want)}, actual {sorted(opts)}")

    if k in ("status_ok", "status_error"):
        mark = "✅" if k == "status_ok" else "❌"
        actual = dc.status_text(side or args.get("target", "A"))
        return mark in actual, (f"status[{side or args.get('target', 'A')}] "
                                f"expected {mark}, actual {actual!r}")

    if k in ("visible", "hidden"):
        name = args.get("target", args.get("of"))
        vis = dc.is_visible(name, side)
        ok = vis if k == "visible" else not vis
        return ok, f"'{name}' visible={vis}, expected {k}"

    if k == "checked":
        name = args.get("target", args.get("of"))
        want = bool(args.get("on", True))
        actual = dc.checkbox(name, side).is_checked()
        return actual == want, f"'{name}' checked={actual}, expected {want}"

    if k == "scrollable":
        # The global CSS pins the app to 100vh/overflow-hidden, so every
        # page must provide its own scroll container — a page without one
        # renders fine on a tall monitor while everything below the fold is
        # unreachable on a small window. Shrink the viewport so content is
        # GUARANTEED to overflow, then verify the container actually
        # scrolls (not just that overflow-y is set).
        sel = args.get("selector") or _PAGE_SCROLL_SELECTOR
        height = int(args.get("height", 500))
        loc = dc.page.locator(sel).first
        if not loc.count():
            return False, f"no scroll container matches {sel!r}"
        orig = dc.page.viewport_size or {"width": 1600, "height": 900}
        try:
            dc.page.set_viewport_size(
                {"width": orig["width"], "height": height})
            dc.page.wait_for_timeout(400)
            info = loc.evaluate(
                "el => { el.scrollTop = el.scrollHeight;"
                " return { overflowY: getComputedStyle(el).overflowY,"
                "          scroll: el.scrollHeight,"
                "          client: el.clientHeight,"
                "          moved: el.scrollTop }; }")
        finally:
            dc.page.set_viewport_size(orig)
            dc.page.wait_for_timeout(200)
        overflows = info["scroll"] > info["client"]
        ok = (info["overflowY"] in ("auto", "scroll")
              and overflows and info["moved"] > 0)
        return ok, (f"container {sel!r} at {height}px viewport: "
                    f"overflowY={info['overflowY']}, "
                    f"scrollHeight={info['scroll']}, "
                    f"clientHeight={info['client']}, "
                    f"scrolledTo={info['moved']}"
                    + ("" if overflows else " — content does not overflow, "
                       "raise the case's content or lower height"))

    raise ValueError(f"unhandled assertion kind: {k}")


# every page-level scroll container class, newest last (see ui.py CSS)
_PAGE_SCROLL_SELECTOR = ".st-lin-page, .st-trp-page, .st-imp-page"
