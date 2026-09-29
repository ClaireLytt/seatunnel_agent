"""Action DSL dispatcher: Step -> DCPage calls.

Each action returns a human-readable detail string for the StepLog.
All DOM knowledge stays in page.py; this file only routes.
"""

from __future__ import annotations

import time
from pathlib import Path

from .models import Step, StepLog
from .page import DCPage


def _ms(t0: float) -> int:
    return int((time.time() - t0) * 1000)


def run_script_step(step: Step, dc: DCPage) -> StepLog:
    """Execute one deterministic step with a single automatic retry."""
    t0 = time.time()
    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            detail = _dispatch(step, dc)
            return StepLog(step.desc, True, _ms(t0),
                           detail + (" (retry)" if attempt == 2 else ""))
        except Exception as e:  # noqa: BLE001 — converted to StepLog
            last_err = e
            if attempt == 1:
                dc.page.wait_for_timeout(700)
    return StepLog(step.desc, False, _ms(t0),
                   f"{type(last_err).__name__}: {last_err}")


def _dispatch(step: Step, dc: DCPage) -> str:
    a, args = step.action, step.args
    side = args.get("side")

    if a == "assert":
        # Mid-steps assertion — for transient states that are gone by the
        # time the expect block runs (e.g. a button disabled DURING a run).
        # args hold exactly one assertion mapping: {kind: {…}}.
        from .asserts import run_assert
        from .loader import _expand_assert
        assertion = _expand_assert(dict(args), "inline assert step")
        log = run_assert(assertion, dc)
        if not log.ok:
            raise AssertionError(log.detail)
        return log.detail

    if a == "goto":
        dc.goto(args.get("target", args.get("path", "/datacompare")))
        return "navigated"

    if a == "click":
        dc.click_button(args["target"], side)
        return f"clicked '{args['target']}'"

    if a == "fill":
        dc.clear_and_type(args["target"], str(args.get("value", "")), side)
        return f"filled '{args['target']}'"

    if a == "clear":
        dc.clear_box(args["target"], side)
        return f"cleared '{args['target']}'"

    if a == "press":
        dc.press_in(args["keys"], args.get("in"), side)
        return f"pressed {args['keys']}"

    if a == "select_ds":
        dc.select_ds(args.get("value", args.get("target")), side or "A")
        return f"ds = {args.get('value', args.get('target'))}"

    if a == "select":
        # {表: value} shorthand or {of:..., value:...}
        name = args.get("of", "选择表")
        value = args.get("value") or args.get("表") or args.get("target")
        dc.dropdown_select(name, str(value), side)
        return f"selected {value!r} in '{name}'"

    if a == "select_index":
        text = dc.dropdown_select_index(
            args.get("of", "选择表"), int(args.get("index", 0)), side)
        return f"selected option[{args.get('index', 0)}] = {text!r}"

    if a == "dropdown_type":
        dc.dropdown_type(args.get("of", "选择表"), str(args.get("text", "")),
                         side)
        return f"typed {args.get('text')!r} in dropdown"

    if a == "check":
        dc.set_checkbox(args["target"], bool(args.get("on", True)), side)
        return f"checkbox '{args['target']}' -> {args.get('on', True)}"

    if a == "slide":
        name = args.get("of", args.get("target"))
        value = args["value"]
        dc.slider(name, side).fill(str(value))
        return f"slider '{name}' -> {value}"

    if a == "open_accordion":
        dc.open_accordion(args["target"])
        return f"opened '{args['target']}'"

    if a == "wait_status_ok":
        text = dc.wait_status(side or args.get("target", "A"), ok=True,
                              timeout_ms=int(args.get("timeout_ms", 20_000)))
        return f"status: {text[:80]}"

    if a == "wait_status_error":
        text = dc.wait_status(side or args.get("target", "A"), ok=False,
                              timeout_ms=int(args.get("timeout_ms", 20_000)))
        return f"status: {text[:80]}"

    if a == "wait_result":
        before = args.get("_before_html")
        timeout = int(args.get("timeout_ms", 30_000))
        if before is not None:
            dc.wait_result_change(before, timeout_ms=timeout)
        else:
            dc.wait_result_stable(timeout_ms=timeout)
        return "result settled"

    if a == "wait_text":
        txt = str(args.get("text", args.get("target", "")))
        dc.wait_for_text(txt, where=args.get("in", "body"),
                         timeout_ms=int(args.get("timeout_ms", 15_000)))
        return f"text appeared: {txt!r}"

    if a == "wait":
        dc.page.wait_for_timeout(int(args.get("ms", 500)))
        return f"waited {args.get('ms')}ms"

    if a == "screenshot":
        name = args.get("name", "manual")
        shots_dir = Path(args.get("_shots_dir", "."))
        shots_dir.mkdir(parents=True, exist_ok=True)
        path = str(shots_dir / f"{name}.png")
        dc.screenshot(path)
        return f"screenshot {name} -> {path}"

    if a == "set_language":
        dc.set_language(args.get("target", args.get("value", "中文")))
        return f"language -> {args.get('target', args.get('value'))}"

    if a == "download":
        path, fname = dc.download(args["target"], args.get("side"))
        return f"downloaded {fname} -> {path}"

    if a == "popup_click":
        text = dc.popup_click(args["target"], args.get("side"))
        return f"popup captured, {len(text)} chars"

    if a == "upload_file":
        path = args.get("path", args.get("file", ""))
        dc.upload_file(args["target"], path, args.get("side"))
        return f"uploaded {path!r} via {args['target']!r}"

    if a == "drag_sidebar":
        width = dc.drag_sidebar_grip(int(args.get("dx", 0)))
        return f"sidebar dragged dx={args.get('dx')} -> width {width}px"

    raise ValueError(f"unhandled action: {a}")
