"""scripts/check_workflow.py 的 floor(禁作弊变绿)规则单测。

直接对 parse_diff / floor_findings 两个纯函数喂合成 diff 文本,
不依赖真实 git 仓库。规则来源:CLAUDE.md 第 10 节 floor 行。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "check_workflow",
    Path(__file__).resolve().parents[1] / "scripts" / "check_workflow.py",
)
assert _SPEC is not None and _SPEC.loader is not None
check_workflow = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_workflow)

parse_diff = check_workflow.parse_diff
floor_findings = check_workflow.floor_findings


def _diff(file: str, added: list[str] | None = None, removed: list[str] | None = None) -> str:
    lines = [f"diff --git a/{file} b/{file}", f"--- a/{file}", f"+++ b/{file}", "@@ -1 +1 @@"]
    lines += ["-" + s for s in (removed or [])]
    lines += ["+" + s for s in (added or [])]
    return "\n".join(lines)


def _findings(diff: str, deleted: list[str] | None = None) -> list[str]:
    added, removed = parse_diff(diff)
    return floor_findings(added, removed, deleted or [])


def test_clean_diff_passes() -> None:
    diff = _diff("src/seatunnel_agent/common/utils.py", added=["x = 1"])
    assert _findings(diff) == []


def test_new_suppression_comment_flagged() -> None:
    for marker in ["x = f()  # noqa", "y: int = z  # type: ignore", "// @ts-ignore",
                   "// eslint-disable-next-line", "/* @ts-nocheck */"]:
        file = "frontend/doctor/src/App.tsx" if "/" in marker[:2] else "src/a.py"
        hits = _findings(_diff(file, added=[marker]))
        assert hits and "压制注释" in hits[0], marker


def test_existing_suppression_untouched_is_ignored() -> None:
    # 存量压制注释只出现在上下文/删除侧,不新增,不应报
    diff = _diff("src/a.py", removed=["x = f()  # noqa"])
    assert all("压制注释" not in f for f in _findings(diff))


def test_pytest_skip_and_xfail_flagged() -> None:
    for deco in ["@pytest.mark.skip(reason='later')", "@pytest.mark.xfail"]:
        hits = _findings(_diff("tests/test_a.py", added=[deco]))
        assert hits and "skip/xfail" in hits[0], deco


def test_deleted_test_file_flagged() -> None:
    hits = _findings("", deleted=["tests/test_gone.py"])
    assert hits == ["[删测试文件] tests/test_gone.py"]


def test_removed_assert_in_surviving_test_flagged() -> None:
    diff = _diff("tests/test_a.py", removed=["    assert result == 3"])
    hits = _findings(diff)
    assert hits and "删断言" in hits[0]


def test_removed_assert_in_deleted_file_not_double_counted() -> None:
    diff = _diff("tests/test_gone.py", removed=["    assert result == 3"])
    hits = _findings(diff, deleted=["tests/test_gone.py"])
    assert hits == ["[删测试文件] tests/test_gone.py"]


def test_mypy_whitelist_shrink_flagged() -> None:
    diff = _diff("pyproject.toml", removed=['    "src/seatunnel_agent/common/sse.py",'])
    hits = _findings(diff)
    assert hits and "mypy白名单缩水" in hits[0]


def test_mypy_whitelist_grow_is_silent() -> None:
    diff = _diff("pyproject.toml", added=['    "src/seatunnel_agent/common/new.py",'])
    assert _findings(diff) == []


def test_stub_and_todo_flagged() -> None:
    hits = _findings(_diff("src/a.py", added=["    raise NotImplementedError"]))
    assert hits and "未完成桩子" in hits[0]
    hits = _findings(_diff("src/a.py", added=["    except Exception: pass"]))
    assert hits and "未完成桩子" in hits[0]
    hits = _findings(_diff("src/a.py", added=["    # TODO: implement"]))
    assert hits and "TODO" in hits[0]


def test_todo_outside_src_is_allowed() -> None:
    assert _findings(_diff("tests/test_a.py", added=["# TODO: more cases"])) == []


def test_out_of_scope_paths_ignored() -> None:
    diff = _diff("docs/reports/20261024-x.md", added=["example:  # noqa"])
    assert _findings(diff) == []


def test_exempt_files_ignored() -> None:
    diff = _diff("scripts/check_workflow.py", added=['PATTERN = "# noqa"'])
    assert _findings(diff) == []
