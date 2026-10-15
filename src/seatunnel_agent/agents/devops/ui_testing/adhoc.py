"""Ad-hoc browser verification: run a one-off steps file without a formal case.

Usage (AI 改完 UI 后快速验证,无需写正式用例文件)::

    seatunnel-agent uitest adhoc --steps /tmp/check.yaml [--url http://127.0.0.1:7860]
        [--page /datacompare] [--screenshot-dir runs/adhoc/foo] [--headed]

steps 文件与正式用例同格式: 既可以是完整用例 (带 id/steps/expect),
也可以是裸的步骤列表 (``- click: 连接``),动作/断言语法与
config/uitest_cases/ 完全一致。每步输出 PASS/FAIL,失败即停但仍截屏,
退出码非 0 表示失败。
"""

from __future__ import annotations

import datetime as _dt
import json
import time
from pathlib import Path

import yaml

from .loader import (
    CASES_DIR,
    CaseLoadError,
    _expand_assert,
    _expand_step,
    _load_fixtures,
)
from .models import CaseResult, Step, TestCase

ADHOC_DIR = Path("runs") / "adhoc"


def load_adhoc_case(path: str | Path, page: str = "") -> TestCase:
    """Parse a steps file into a synthetic TestCase (reuses the case parser).

    Accepted shapes (YAML or JSON):
    - a bare list of steps: ``[- click: 连接, ...]``
    - a mapping with optional ``page`` / ``steps`` / ``expect`` keys
    - a full case mapping (or 1-element list) as in config/uitest_cases/
    """
    p = Path(path)
    if not p.is_file():
        raise CaseLoadError(f"steps 文件不存在: {p}")
    text = p.read_text(encoding="utf-8")
    try:
        raw = (json.loads(text) if p.suffix.lower() == ".json"
               else yaml.safe_load(text)) or []
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        raise CaseLoadError(f"{p.name}: 解析失败: {e}")

    if isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], dict) \
            and ("steps" in raw[0] or "expect" in raw[0] or "id" in raw[0]):
        raw = raw[0]                      # 1-case file -> the case mapping
    if isinstance(raw, list):
        raw = {"steps": raw}              # bare step list
    if not isinstance(raw, dict):
        raise CaseLoadError(f"{p.name}: 顶层须为步骤列表或用例映射")

    fixtures = _load_fixtures(CASES_DIR)
    ctx = p.name
    steps: list[Step] = []
    for s in raw.get("setup") or []:
        steps.extend(_expand_step(s, fixtures, ctx + "/setup"))
    for s in raw.get("steps") or []:
        steps.extend(_expand_step(s, fixtures, ctx + "/steps"))
    expect = [_expand_assert(a, ctx + "/expect")
              for a in raw.get("expect") or []]
    if not steps and not expect:
        raise CaseLoadError(f"{p.name}: 没有任何步骤或断言")
    if any(s.ai for s in steps) or any(a.kind == "ai_judge" for a in expect):
        raise CaseLoadError(f"{p.name}: adhoc 模式不支持 ai 步骤 / ai_judge 断言")

    return TestCase(
        id=str(raw.get("id", "ADHOC")),
        title=str(raw.get("title", f"ad-hoc: {p.name}")),
        tags=["sqlite"],
        page=page or str(raw.get("page", "/datacompare")),
        lang=str(raw.get("lang", "zh")),
        steps=steps,
        expect=expect,
        timeout_s=int(raw.get("timeout_s", 120)),
    )


def run_adhoc(steps_file: str | Path, url: str = "", page: str = "",
              screenshot_dir: str | Path | None = None, headed: bool = False,
              port: int | None = None) -> tuple[CaseResult, Path]:
    """Run one ad-hoc case; returns (result, shots_dir).  No LLM involved."""
    from playwright.sync_api import sync_playwright

    from .env import DEFAULT_PORT, AppUnderTest
    from .page import DCPage
    from .runner import _snap, run_case

    case = load_adhoc_case(steps_file, page=page)
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    shots_dir = Path(screenshot_dir) if screenshot_dir else ADHOC_DIR / ts
    shots_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    with AppUnderTest(port=port or DEFAULT_PORT, log_dir=shots_dir,
                      external_url=url) as app:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not headed)
            pg = browser.new_page(viewport={"width": 1600, "height": 900})
            pg.set_default_timeout(10_000)
            dc = DCPage(pg, app.base_url)
            res = run_case(case, dc, llm=None, shots_dir=shots_dir)
            # always leave a final full-page screenshot for the caller
            final = _snap(dc, shots_dir, case.id, "final")
            browser.close()
    if final:
        from .models import StepLog
        res.asserts.append(StepLog(desc="最终截图", ok=True, elapsed_ms=0,
                                   screenshot=final))
    res.elapsed_ms = int((time.time() - t0) * 1000)
    return res, shots_dir
