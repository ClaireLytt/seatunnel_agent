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


def test_assert_locator_tightening_is_an_update() -> None:
    # addressing detail changed, compared value identical -> not a deletion
    diff = _diff(
        "tests/test_a.py",
        removed=['    assert page.locator("input").input_value() == "demo"'],
        added=['    assert page.locator("input:not([type=checkbox])")'
               '.input_value() == "demo"'],
    )
    assert _findings(diff) == []


def test_new_workspace_without_lockfile_flagged() -> None:
    added = [("frontend/package.json", '    "contract_check",')]
    hits = check_workflow.frontend_lock_findings(
        added, ["frontend/package.json"])
    assert hits and "锁文件未更新" in hits[0]


def test_new_workspace_with_lockfile_passes() -> None:
    added = [("frontend/package.json", '    "contract_check",')]
    assert check_workflow.frontend_lock_findings(
        added, ["frontend/package.json", "frontend/package-lock.json"]) == []


def test_dependency_line_not_mistaken_for_workspace() -> None:
    added = [("frontend/package.json", '    "vite": "^6.0.7",')]
    assert check_workflow.frontend_lock_findings(
        added, ["frontend/package.json"]) == []


def test_assert_glyph_swap_is_an_update() -> None:
    # mark migrations swap a non-ASCII glyph inside the asserted string;
    # the ASCII expectation is unchanged -> an update, not a deletion
    diff = _diff(
        "tests/test_a.py",
        removed=['    assert "⛔ skew confirmed" in en'],
        added=['    assert "● skew confirmed" in en'],
    )
    assert _findings(diff) == []
    # dropping a decorative emoji prefix is the same presentation move
    diff2 = _diff(
        "tests/test_a.py",
        removed=['    assert "⚠️ 2 条告警" in titles'],
        added=['    assert "2 条告警" in titles'],
    )
    assert _findings(diff2) == []


def test_assert_ascii_expectation_still_protected() -> None:
    # the glyph rule must not excuse a changed ASCII expectation
    diff = _diff(
        "tests/test_a.py",
        removed=['    assert "● skew confirmed" in en'],
        added=['    assert "● skew denied" in en'],
    )
    hits = _findings(diff)
    assert hits and "删断言" in hits[0]


def test_assert_magic_number_rederived_is_an_update() -> None:
    # "== 14" replaced by "== <expression>" on the same compared value:
    # the hand-synced constant now comes from its source of truth
    diff = _diff(
        "tests/test_a.py",
        removed=["    assert len(run(s2.list_tools)) == 14"],
        added=["    assert len(run(s2.list_tools)) == expected"],
    )
    assert _findings(diff) == []


def test_assert_rederive_needs_same_lhs() -> None:
    # a different compared value is a new assertion, not an update
    diff = _diff(
        "tests/test_a.py",
        removed=["    assert len(run(s2.list_tools)) == 14"],
        added=["    assert len(other) == expected"],
    )
    hits = _findings(diff)
    assert hits and "删断言" in hits[0]


def test_assert_rederive_only_for_numeric_literals() -> None:
    # a non-numeric expectation swapped for an expression stays flagged
    diff = _diff(
        "tests/test_a.py",
        removed=['    assert out == "demo"'],
        added=["    assert out == anything()"],
    )
    hits = _findings(diff)
    assert hits and "删断言" in hits[0]


def test_assert_expected_value_change_still_flagged() -> None:
    # the selector rule must not excuse a weakened expectation
    diff = _diff(
        "tests/test_a.py",
        removed=['    assert page.locator("input").input_value() == "demo"'],
        added=['    assert page.locator("input").input_value() != "demo"'],
    )
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


# ----------------------------------------------------------------------
# report must paste check_workflow output (CLAUDE.md section 7)
# ----------------------------------------------------------------------

_REPORT_CHECK = check_workflow.check_report_has_workflow_output


def _fake_git(files: list[str]):
    def inner(*args: str) -> str:
        if args[0] == "diff":
            return "\n".join(files)
        return ""
    return inner


def test_report_with_pasted_output_passes(tmp_path, monkeypatch) -> None:
    rpt = tmp_path / "docs" / "reports" / "20260101-x.md"
    rpt.parent.mkdir(parents=True)
    rpt.write_text(
        "## check\npython scripts/check_workflow.py\n[PASS] ok\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        check_workflow, "_git", _fake_git(["docs/reports/20260101-x.md"]),
    )
    ok, msg = _REPORT_CHECK("origin/main...HEAD")
    assert ok, msg


def test_report_with_placeholder_fails(tmp_path, monkeypatch) -> None:
    rpt = tmp_path / "docs" / "reports" / "20260101-x.md"
    rpt.parent.mkdir(parents=True)
    rpt.write_text("check_workflow -> (output in chat)\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        check_workflow, "_git", _fake_git(["docs/reports/20260101-x.md"]),
    )
    ok, msg = _REPORT_CHECK("origin/main...HEAD")
    assert not ok and "20260101-x.md" in msg


def test_no_new_report_is_silent(monkeypatch) -> None:
    monkeypatch.setattr(check_workflow, "_git", _fake_git(["src/x.py"]))
    ok, _ = _REPORT_CHECK("origin/main...HEAD")
    assert ok


def test_no_remote_range_skips() -> None:
    ok, _ = _REPORT_CHECK(None)
    assert ok


def test_floor_assert_number_update_not_flagged():
    """Changing only the numeric expectation of an assert (count grows with
    the code) is an update, not a deleted assertion; dropping the assert
    outright still flags."""
    from scripts.check_workflow import floor_findings

    updated = floor_findings(
        added=[("tests/test_x.py", "    assert len(tools) == 9")],
        removed=[("tests/test_x.py", "    assert len(tools) == 8")],
        deleted_files=[],
    )
    assert updated == []

    dropped = floor_findings(
        added=[],
        removed=[("tests/test_x.py", "    assert len(tools) == 8")],
        deleted_files=[],
    )
    assert any("test_x.py" in f for f in dropped)

    # a different assert added nearby does not excuse the deletion
    swapped = floor_findings(
        added=[("tests/test_x.py", "    assert tools")],
        removed=[("tests/test_x.py", "    assert len(tools) == 8")],
        deleted_files=[],
    )
    assert any("test_x.py" in f for f in swapped)
