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

    if k == "options_not_contains":
        # negative membership: the only order-independent contract for a
        # shared store (asserting exact lists or emptiness couples the case
        # to whatever OTHER cases saved earlier in the suite)
        name = args.get("of")
        value = str(args.get("value", ""))
        keep = bool(args.get("keep_filter", False))
        opts = dc.dropdown_options(name, side, keep_filter=keep)
        return value not in opts, (
            f"'{name}' options {'do NOT' if value not in opts else 'DO'} "
            f"contain {value!r}: {opts}")

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

    if k == "enabled":
        # interactive-state check: guards run-time button disabling (e.g.
        # the double-click guard on slow compare buttons)
        name = args.get("target", args.get("of"))
        want = bool(args.get("on", True))
        actual = dc.button(name, side).is_enabled()
        return actual == want, f"'{name}' enabled={actual}, expected {want}"

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
                " const r = el.getBoundingClientRect();"
                " return { overflowY: getComputedStyle(el).overflowY,"
                "          scroll: el.scrollHeight,"
                "          client: el.clientHeight,"
                "          moved: el.scrollTop,"
                "          bottomGap: window.innerHeight - r.bottom }; }")
        finally:
            dc.page.set_viewport_size(orig)
            dc.page.wait_for_timeout(200)
        overflows = info["scroll"] > info["client"]
        # bottomGap < 0 means the container's bottom strip hangs below the
        # viewport inside a clipped ancestor: that strip (and its widgets,
        # e.g. a slider at the end of the sidebar) is unreachable even at
        # full scroll — a 100vh container under the navbar does exactly
        # this.
        clipped = info["bottomGap"] < -2
        ok = (info["overflowY"] in ("auto", "scroll")
              and overflows and info["moved"] > 0 and not clipped)
        return ok, (f"container {sel!r} at {height}px viewport: "
                    f"overflowY={info['overflowY']}, "
                    f"scrollHeight={info['scroll']}, "
                    f"clientHeight={info['client']}, "
                    f"scrolledTo={info['moved']}, "
                    f"bottomGap={info['bottomGap']:.1f}px"
                    + (" — bottom strip clipped by an ancestor"
                       if clipped else "")
                    + ("" if overflows else " — content does not overflow, "
                       "raise the case's content or lower height"))

    if k == "result_in_view":
        # Geometry guard: the result card must actually be VISIBLE, not just
        # present in the DOM. Regression source: .st-main is a fixed-height
        # flex column, and with flex-wrap:wrap a card taller than the
        # viewport got wrapped into a second column OUTSIDE the container,
        # then clipped by overflow:hidden — every text assert stayed green
        # while the user saw a blank panel. Shrink the viewport width so a
        # tall card is guaranteed to overflow, then check the card's box
        # stays inside .st-main and is not covered by an overlay.
        width = int(args.get("width", 950))
        loc = dc.result_container()
        if not loc.count():
            return False, "no result card found"
        orig = dc.page.viewport_size or {"width": 1600, "height": 900}
        try:
            dc.page.set_viewport_size({"width": width, "height": orig["height"]})
            dc.page.wait_for_timeout(400)
            # Driving bottom-of-sidebar controls leaves window/container
            # scroll behind (seen on scroll-page layouts: the row top sat a
            # few px above the viewport, elementFromPoint returned null and
            # read as "covered"). Reset VERTICAL scroll only and clamp the
            # probe point into the viewport — horizontal scroll/geometry is
            # untouched, so the flex-wrap-outside-.st-main regression this
            # assert exists for cannot be masked.
            info = loc.evaluate(
                "el => {"
                " for (let n = el; n; n = n.parentElement) {"
                "   if (n.scrollTop) n.scrollTop = 0; }"
                " window.scrollTo(window.scrollX, 0);"
                " const main = el.closest('.st-main') || el.parentElement;"
                " const r = el.getBoundingClientRect();"
                " const m = main.getBoundingClientRect();"
                " const x = Math.min(Math.max(r.left + 8, m.left + 2), m.right - 2);"
                " const y = Math.min(Math.max(r.top + 8, m.top + 2, 2),"
                "                    window.innerHeight - 2, r.bottom - 2);"
                " const hit = document.elementFromPoint(x, y);"
                " return { left: r.left, width: r.width, height: r.height,"
                "          mLeft: m.left, mRight: m.right,"
                "          covered: !(hit && el.contains(hit)) }; }")
        finally:
            dc.page.set_viewport_size(orig)
            dc.page.wait_for_timeout(200)
        main_w = info["mRight"] - info["mLeft"]
        inside = (info["left"] >= info["mLeft"] - 2
                  and info["left"] < info["mRight"]
                  and info["width"] > main_w * 0.5)
        ok = inside and info["height"] > 0 and not info["covered"]
        return ok, (f"result card at {width}px viewport: "
                    f"left={info['left']:.0f} width={info['width']:.0f} "
                    f"height={info['height']:.0f} "
                    f"main=[{info['mLeft']:.0f},{info['mRight']:.0f}] "
                    f"covered={info['covered']}"
                    + ("" if ok else
                       " — card rendered outside the visible main column"))

    if k == "perf_budget":
        # Performance regression guard: the compare summary prints the
        # server-side elapsed time ("耗时 12345ms" / "elapsed 12345ms") —
        # bound it. Budgets are deliberately loose (catch gross
        # serialization regressions, not CI jitter).
        import re as _re
        budget = int(args.get("ms", 60000))
        text = dc.result_text()
        m = _re.search(r"(?:耗时|elapsed)\s*(\d+)\s*ms", text)
        if not m:
            return False, "no elapsed-ms figure found in the result area"
        actual = int(m.group(1))
        return actual <= budget, (
            f"server elapsed {actual}ms vs budget {budget}ms")

    if k == "result_stable":
        # The result panel must not re-render within the window — guards
        # trigger_mode="once" on slow buttons: a duplicate queued run would
        # repaint the panel with a different elapsed-ms summary.
        ms = int(args.get("ms", 12000))
        before = dc.result_container().inner_html()
        dc.page.wait_for_timeout(ms)
        after = dc.result_container().inner_html()
        return before == after, (
            f"result panel {'unchanged' if before == after else 'RE-RENDERED'} "
            f"within {ms}ms window")

    if k == "visual_baseline":
        # Pixel-level regression against a stored baseline screenshot of the
        # result card. Geometry asserts (result_in_view) still miss
        # white-on-white text, z-index overlays and font collapse; a pixel
        # diff catches those. Rendering differs across OS/font stacks, so
        # this only runs when UITEST_VISUAL=1 (baselines are per-machine);
        # otherwise it passes with a note instead of flaking CI.
        import os
        name = str(args.get("name", ""))
        if not name:
            return False, "visual_baseline requires a 'name' argument"
        if os.getenv("UITEST_VISUAL") != "1":
            return True, f"visual baseline {name!r} skipped (set UITEST_VISUAL=1)"
        threshold = float(args.get("threshold", 0.03))
        loc = dc.result_container()
        if not loc.count():
            return False, "no result card found"
        png = loc.screenshot()

        from pathlib import Path as _P
        base_dir = _P(__file__).parent / "baselines"
        base_dir.mkdir(exist_ok=True)
        base_path = base_dir / f"{name}.png"
        if not base_path.exists():
            base_path.write_bytes(png)
            return True, f"baseline created: {base_path}"

        import io as _io

        from PIL import Image
        actual = Image.open(_io.BytesIO(png)).convert("RGB")
        expected = Image.open(base_path).convert("RGB")
        if actual.size != expected.size:
            actual = actual.resize(expected.size)
        pa, pe = actual.tobytes(), expected.tobytes()
        diff = sum(1 for x, y in zip(pa, pe) if abs(x - y) > 24)
        ratio = diff / max(len(pe), 1)
        ok = ratio <= threshold
        if not ok:
            fail_path = base_dir / f"{name}.actual.png"
            fail_path.write_bytes(png)
            return False, (f"visual diff {ratio:.1%} > {threshold:.1%} "
                           f"vs {base_path.name}; actual saved to {fail_path}")
        return True, f"visual diff {ratio:.1%} <= {threshold:.1%}"

    if k == "download_ok":
        if not dc.last_download:
            return False, "no download captured — run a 'download' step first"
        path, fname = dc.last_download
        ext = str(args.get("ext", ""))
        if ext and not fname.lower().endswith(ext.lower()):
            return False, f"filename {fname!r} does not end with {ext!r}"
        from pathlib import Path as _P
        data = _P(path).read_bytes()
        min_bytes = int(args.get("min_bytes", 1))
        if len(data) < min_bytes:
            return False, f"{fname}: {len(data)} bytes < min_bytes {min_bytes}"
        magic = str(args.get("magic", ""))
        if magic and not data.startswith(magic.encode("utf-8")):
            return False, (f"{fname}: leading bytes {data[:8]!r} do not match "
                           f"magic {magic!r}")
        needle = str(args.get("text", ""))
        if needle:
            body = data.decode("utf-8", errors="ignore")
            if needle.casefold() not in body.casefold():
                return False, (f"{fname}: content does not contain {needle!r}; "
                               f"head={body[:200]!r}")
        return True, f"download ok: {fname} ({len(data)} bytes)"

    if k == "popup_contains":
        if dc.last_popup_text is None:
            return False, "no popup captured — run a 'popup_click' step first"
        needle = str(args.get("text", args.get("target", "")))
        found = needle.casefold() in dc.last_popup_text.casefold()
        snippet = dc.last_popup_text[:300]
        return found, (f"popup does{'' if found else ' not'} contain "
                       f"{needle!r}; text={snippet!r}")

    if k == "sidebar_width":
        width = dc.sidebar_width()
        lo = int(args.get("min", 0))
        hi = int(args.get("max", 10**9))
        max_vw = args.get("max_vw")
        if max_vw is not None:
            inner = int(dc.page.evaluate("() => window.innerWidth"))
            hi = min(hi, int(inner * float(max_vw) / 100) + 2)  # rounding slack
        ok = lo <= width <= hi
        return ok, f"sidebar width {width}px (expected {lo}..{hi}px)"

    raise ValueError(f"unhandled assertion kind: {k}")


# every page-level scroll container class, newest last (see ui.py CSS)
_PAGE_SCROLL_SELECTOR = ".st-lin-page, .st-trp-page, .st-imp-page, .st-mig-page"
