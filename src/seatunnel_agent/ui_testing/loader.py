"""YAML case loading, shorthand expansion, schema validation, tag filtering.

Shorthand rules (see docs/ui_test_agent_design.md §3):

- ``click: 连接``                → ``{action: click, args: {target: 连接}}``
- ``fill: {主机: 1.2.3.4}``      → one fill step per key
- ``ai: 打开下拉框...``          → LLM step
- ``use: connect_both_sqlite``   → splice the fixture's steps in
- assertions: ``text_contains: {in: 状态, text: ...}`` /
  ``ai_judge: 差异单元格高亮`` (bare string allowed)

Unknown actions or assertion kinds are rejected at load time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import Assertion, Step, TestCase

CASES_DIR = Path(__file__).parent / "cases"

KNOWN_ACTIONS = frozenset({
    "goto", "click", "fill", "clear", "press", "select_ds", "select",
    "dropdown_type", "check", "open_accordion", "wait_status_ok",
    "wait_status_error", "wait_result", "wait", "screenshot", "set_language",
})

KNOWN_ASSERTS = frozenset({
    "text_contains", "text_not_contains", "value_is", "options_are",
    "options_count", "status_ok", "status_error", "visible", "hidden",
    "checked", "ai_judge",
})

KNOWN_TAGS = frozenset({"smoke", "full", "hive", "sqlite", "slow", "manual"})

# fill targets whose values must never be inlined in YAML
_FORBIDDEN_FILL_TARGETS = frozenset({"密码", "password", "Password"})


class CaseLoadError(ValueError):
    """A case file failed validation — message says file/case/why."""


def _expand_step(raw: Any, fixtures: dict[str, list[dict]],
                 ctx: str) -> list[Step]:
    """One raw YAML step -> one or more Steps (fixtures splice in several)."""
    if not isinstance(raw, dict) or not raw:
        raise CaseLoadError(f"{ctx}: step must be a non-empty mapping, got {raw!r}")

    if "use" in raw:
        name = raw["use"]
        if name not in fixtures:
            raise CaseLoadError(f"{ctx}: unknown fixture {name!r}")
        out: list[Step] = []
        for sub in fixtures[name]:
            out.extend(_expand_step(sub, fixtures, f"{ctx}/use:{name}"))
        return out

    if "ai" in raw:
        return [Step(ai=str(raw["ai"]), note=str(raw.get("note", "")))]

    # long form: {action: click, args: {...}}
    if "action" in raw:
        action = raw["action"]
        args = dict(raw.get("args") or {})
    else:
        # shorthand: single key {动作: 值}, plus optional note
        keys = [k for k in raw if k != "note"]
        if len(keys) != 1:
            raise CaseLoadError(f"{ctx}: ambiguous step {raw!r}")
        action = keys[0]
        val = raw[action]
        if isinstance(val, dict):
            args = dict(val)
        elif action == "fill":
            raise CaseLoadError(f"{ctx}: fill needs a mapping {{标签: 值}}")
        elif action == "wait":
            args = {"ms": int(val)}
        elif action == "press":
            args = {"keys": str(val)}
        elif action in ("wait_status_ok", "wait_status_error"):
            args = {"side": str(val)}
        else:
            args = {"target": val}

    # YAML 1.1 parses a bare `on:` key as boolean True — map it back
    if True in args:
        args["on"] = args.pop(True)

    if action not in KNOWN_ACTIONS:
        raise CaseLoadError(f"{ctx}: unknown action {action!r} "
                            f"(known: {sorted(KNOWN_ACTIONS)})")
    if action == "wait" and not raw.get("note"):
        raise CaseLoadError(f"{ctx}: bare 'wait' requires a note explaining why")

    # fill with several labels expands to one step per label so each gets
    # its own StepLog line
    if action == "fill":
        side = args.pop("side", None)
        pairs = [(k, v) for k, v in args.items()]
        if not pairs:
            raise CaseLoadError(f"{ctx}: fill with no fields")
        steps = []
        for label, value in pairs:
            if label in _FORBIDDEN_FILL_TARGETS or "password" in label.lower():
                raise CaseLoadError(
                    f"{ctx}: refusing inline credential for {label!r} — "
                    "use .env instead")
            a = {"target": label, "value": value}
            if side is not None:
                a["side"] = side
            steps.append(Step(action="fill", args=a,
                              note=str(raw.get("note", ""))))
        return steps

    return [Step(action=action, args=args, note=str(raw.get("note", "")))]


def _expand_assert(raw: Any, ctx: str) -> Assertion:
    if isinstance(raw, dict):
        keys = [k for k in raw if k != "note"]
        if "kind" in raw:
            kind, args = raw["kind"], dict(raw.get("args") or {})
        elif len(keys) == 1:
            kind = keys[0]
            val = raw[kind]
            if kind == "ai_judge":
                args = {"expect": str(val)} if not isinstance(val, dict) else dict(val)
            elif isinstance(val, dict):
                args = dict(val)
            else:
                args = {"target": val}
        else:
            raise CaseLoadError(f"{ctx}: ambiguous assertion {raw!r}")
        note = str(raw.get("note", ""))
    else:
        raise CaseLoadError(f"{ctx}: assertion must be a mapping, got {raw!r}")

    if kind not in KNOWN_ASSERTS:
        raise CaseLoadError(f"{ctx}: unknown assertion {kind!r} "
                            f"(known: {sorted(KNOWN_ASSERTS)})")
    return Assertion(kind=kind, args=args, note=note)


def _load_fixtures(cases_dir: Path) -> dict[str, list[dict]]:
    path = cases_dir / "_fixtures.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise CaseLoadError(f"{path.name}: fixtures file must be a mapping")
    return data


def load_cases(cases_dir: Path | str = CASES_DIR) -> list[TestCase]:
    """Load and validate every case file.  Order: file name, then position."""
    cases_dir = Path(cases_dir)
    fixtures = _load_fixtures(cases_dir)
    cases: list[TestCase] = []
    seen_ids: set[str] = set()

    for path in sorted(cases_dir.glob("*.yaml")):
        if path.name.startswith("_fixtures"):
            continue
        raw_list = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(raw_list, list):
            raise CaseLoadError(f"{path.name}: top level must be a list of cases")
        for raw in raw_list:
            ctx = f"{path.name}"
            if not isinstance(raw, dict) or "id" not in raw:
                raise CaseLoadError(f"{ctx}: case missing 'id': {raw!r}")
            cid = str(raw["id"])
            ctx = f"{path.name}:{cid}"
            if cid in seen_ids:
                raise CaseLoadError(f"{ctx}: duplicate case id")
            seen_ids.add(cid)

            tags = [str(t) for t in (raw.get("tags") or [])]
            unknown = set(tags) - KNOWN_TAGS
            if unknown:
                raise CaseLoadError(f"{ctx}: unknown tags {sorted(unknown)}")
            if "manual" not in tags and not ({"sqlite", "hive"} & set(tags)):
                raise CaseLoadError(f"{ctx}: needs tag 'sqlite' or 'hive'")

            setup: list[Step] = []
            for s in raw.get("setup") or []:
                setup.extend(_expand_step(s, fixtures, ctx + "/setup"))
            steps: list[Step] = []
            for s in raw.get("steps") or []:
                steps.extend(_expand_step(s, fixtures, ctx + "/steps"))
            expect = [_expand_assert(a, ctx + "/expect")
                      for a in raw.get("expect") or []]

            if "manual" not in tags and not steps and not setup:
                raise CaseLoadError(f"{ctx}: automated case has no steps")

            cases.append(TestCase(
                id=cid,
                title=str(raw.get("title", "")),
                tags=tags,
                page=str(raw.get("page", "/datacompare")),
                lang=str(raw.get("lang", "zh")),
                setup=setup,
                steps=steps,
                expect=expect,
                timeout_s=int(raw.get("timeout_s", 90)),
            ))
    return cases


def filter_cases(cases: list[TestCase], suite: str = "",
                 case_ids: list[str] | None = None) -> list[TestCase]:
    """Select cases by explicit ids (priority) or suite tag."""
    if case_ids:
        wanted = {c.upper() for c in case_ids}
        picked = [c for c in cases if c.id.upper() in wanted]
        missing = wanted - {c.id.upper() for c in picked}
        if missing:
            raise CaseLoadError(f"unknown case id(s): {sorted(missing)}")
        return picked
    if not suite:
        suite = "smoke"
    if suite == "full":
        # everything automated that doesn't need special environments
        return [c for c in cases
                if "manual" not in c.tags and "hive" not in c.tags
                and "slow" not in c.tags]
    return [c for c in cases if suite in c.tags and "manual" not in c.tags]
