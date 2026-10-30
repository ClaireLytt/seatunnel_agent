"""批次工作流机械核对(CLAUDE.md 第 7 节)。

检查项:
1. 未推送 commit 的提交信息中无 AI 署名(Co-Authored-By / Generated with)。
2. git 工作区干净(不允许留下未提交的修改)。
3. 未推送 commit 若改动了 src/ 或 tests/,docs/reports/ 中必须同批提交了新报告。
4. 禁作弊变绿(floor,只看 diff 新增/删除,存量不管;收紧静默、放水报警):
   - 新增压制注释(# noqa / # type: ignore / @ts-ignore / @ts-nocheck / eslint-disable)
   - 测试放水(新增 skip/xfail、删测试文件、存活测试文件中删 assert)
   - pyproject [tool.mypy] files 白名单缩水
   - 未完成桩子(raise NotImplementedError、单行空 except: pass、src/ 新增 TODO)

用法:python scripts/check_workflow.py [--range <rev-range>]
本地默认核对 origin/main...HEAD(与 CI 同口径);CI 中传 --range origin/<base>...HEAD。
任一项 FAIL 时退出码非 0,本批次不得标记完成。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_TRAILERS = ("co-authored-by", "generated with")

# ---------------- floor(禁作弊变绿)----------------
# 只扫代码路径;本文件与其单测含有规则样本字符串,豁免。
FLOOR_SCOPE = ("src/", "tests/", "scripts/", "frontend/", "pyproject.toml")
FLOOR_EXEMPT = ("scripts/check_workflow.py", "tests/test_check_workflow_floor.py")

RE_SUPPRESS = re.compile(
    r"#\s*noqa|#\s*type:\s*ignore|@ts-ignore|@ts-nocheck|eslint-disable"
)
RE_TEST_SKIP = re.compile(r"@pytest\.mark\.(skip|xfail)")
RE_STUB = re.compile(r"raise\s+NotImplementedError|except[^:\n]*:\s*pass\b")
RE_TODO = re.compile(r"\bTODO\b")
RE_MYPY_FILE = re.compile(r'^\s*"src/')


def _in_floor_scope(path: str) -> bool:
    return path.startswith(FLOOR_SCOPE) and path not in FLOOR_EXEMPT


def parse_diff(diff: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """把 unified diff 解析为 (新增行, 删除行),各元素为 (文件路径, 行文本)。

    仅 hunk 外的 ---/+++ 是文件头;hunk 内每行都是内容。
    """
    added: list[tuple[str, str]] = []
    removed: list[tuple[str, str]] = []
    file = ""
    in_header = False
    for line in diff.splitlines():
        if line.startswith("diff "):
            in_header = True
        elif line.startswith("@@"):
            in_header = False
        elif in_header:
            if line.startswith("+++ "):
                path = line[4:].strip()
                if path != "/dev/null":
                    file = re.sub(r"^b/", "", path)
        elif line.startswith("+"):
            added.append((file, line[1:]))
        elif line.startswith("-"):
            removed.append((file, line[1:]))
    return added, removed


_RE_LOCATOR_ARG = re.compile(
    r"""(locator|get_by_placeholder|get_by_text|get_by_label)\(\s*"""
    r"""(?P<q>["'])(?:(?!(?P=q)).)*(?P=q)"""
)


def _assert_shape(text: str) -> str:
    """Normalized form of an assert line: digits (counts drift as code grows),
    element-addressing selector strings (tightening a locator is an
    addressing detail, not an expectation change — the compared value keeps
    full protection because only the selector argument is blanked), and
    non-ASCII glyphs plus whitespace (mark/emoji migrations swap a glyph
    inside the asserted string; every ASCII word stays protected)."""
    import re as _re

    s = _re.sub(r"\d+", "#", text.strip())
    s = _RE_LOCATOR_ARG.sub(r"\1(<sel>", s)
    s = _re.sub(r"[^\x00-\x7f]+", "", s)
    return _re.sub(r"\s+", "", s)


def _split_eq(text: str) -> tuple[str, str] | None:
    """``assert LHS == RHS`` → (LHS, RHS); None for any other assert."""
    s = text.strip()
    if not s.startswith("assert ") or "==" not in s:
        return None
    lhs, _, rhs = s.partition("==")
    return lhs, rhs.strip()


def _assert_updated(
    file: str, removed_text: str, added: list[tuple[str, str]]
) -> bool:
    """True when the same file gains an assert that differs only in numbers —
    an updated expectation, not a deleted one. A ``== <magic number>``
    expectation re-derived as an expression over the same compared value
    (same LHS, still ``==``) also counts: the comparison survives, only the
    hand-synced constant is replaced by its source of truth."""
    import re as _re

    shape = _assert_shape(removed_text)
    for f, a in added:
        if f == file and a.lstrip().startswith("assert ") and _assert_shape(a) == shape:
            return True
    removed_eq = _split_eq(removed_text)
    if removed_eq and _re.fullmatch(r"\d+", removed_eq[1]):
        for f, a in added:
            added_eq = _split_eq(a) if f == file else None
            if added_eq and _assert_shape(added_eq[0]) == _assert_shape(removed_eq[0]):
                return True
    return False


def floor_findings(
    added: list[tuple[str, str]],
    removed: list[tuple[str, str]],
    deleted_files: list[str],
) -> list[str]:
    """按 CLAUDE.md 第 10 节 floor 规则产出违规清单(空 = 干净)。"""
    findings: list[str] = []
    deleted_tests = [
        f for f in deleted_files if f.startswith("tests/test_") and f not in FLOOR_EXEMPT
    ]
    for f in deleted_tests:
        findings.append(f"[删测试文件] {f}")
    for file, text in added:
        if not _in_floor_scope(file):
            continue
        if RE_SUPPRESS.search(text):
            findings.append(f"[新增压制注释] {file}: {text.strip()[:80]}")
        if file.startswith("tests/") and RE_TEST_SKIP.search(text):
            findings.append(f"[测试skip/xfail] {file}: {text.strip()[:80]}")
        if RE_STUB.search(text):
            findings.append(f"[未完成桩子] {file}: {text.strip()[:80]}")
        if file.startswith("src/") and RE_TODO.search(text):
            findings.append(f"[TODO顶实现] {file}: {text.strip()[:80]}")
    for file, text in removed:
        if not _in_floor_scope(file):
            continue
        if (
            file.startswith("tests/")
            and file not in deleted_tests
            and text.lstrip().startswith("assert ")
            and not _assert_updated(file, text, added)
        ):
            findings.append(f"[删断言] {file}: {text.strip()[:80]}")
        if file == "pyproject.toml" and RE_MYPY_FILE.match(text):
            findings.append(f"[mypy白名单缩水] pyproject.toml: {text.strip()[:80]}")
    return findings


def check_floor(rng: str | None) -> tuple[bool, str]:
    if rng is None:
        return True, "无远端分支,跳过 floor 检查"
    diff = _git("diff", "--unified=0", rng)
    deleted_files = _git("diff", "--name-only", "--diff-filter=D", rng).splitlines()
    added, removed = parse_diff(diff)
    findings = floor_findings(added, removed, deleted_files)
    if findings:
        return False, f"发现 {len(findings)} 处降低门槛的改动(范围 {rng}):\n" + "\n".join(
            "  " + f for f in findings
        )
    return True, f"无作弊变绿改动(范围 {rng})"


_RE_WORKSPACE_ENTRY = re.compile(r'^\s*"[\w-]+",?\s*$')


def frontend_lock_findings(
    added: list[tuple[str, str]], changed_files: list[str]
) -> list[str]:
    """New frontend workspace entries must ship the regenerated lock file.

    教训(2026-10-29):contract_check workspace 进了 package.json 但
    package-lock.json 没跟上,CI 的 `npm ci` 直接红。workspace 条目是
    纯名字行(不含冒号),devDependencies 之类的 "k": "v" 行不误伤。"""
    ws_added = [
        text.strip()
        for file, text in added
        if file == "frontend/package.json" and _RE_WORKSPACE_ENTRY.match(text)
    ]
    if ws_added and "frontend/package-lock.json" not in changed_files:
        return [
            f"[锁文件未更新] frontend/package.json 新增 workspace {t} "
            "但 package-lock.json 未变(先跑 cd frontend && npm install)"
            for t in ws_added
        ]
    return []


def check_frontend_lock(rng: str | None) -> tuple[bool, str]:
    if rng is None:
        return True, "无远端分支,跳过锁文件检查"
    diff = _git("diff", "--unified=0", rng, "--", "frontend/package.json")
    changed_files = _git("diff", "--name-only", rng).splitlines()
    added, _ = parse_diff(diff)
    findings = frontend_lock_findings(added, changed_files)
    if findings:
        return False, "\n".join("  " + f for f in findings)
    return True, f"workspace 与锁文件同步(范围 {rng})"


def _git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return out.stdout


def _unpushed_range() -> str | None:
    branch = _git("rev-parse", "--abbrev-ref", "HEAD").strip()
    try:
        _git("rev-parse", "--verify", f"origin/{branch}")
    except subprocess.CalledProcessError:
        return None  # 无远端分支:视全部提交为未推送没有意义,跳过范围检查
    return f"origin/{branch}..HEAD"


def _default_range() -> str | None:
    """本地默认范围与 CI 对齐:优先 origin/main...HEAD(整个分支)。

    教训(pitfalls 2026-10-24):push 后 origin/<branch>..HEAD 是空集,
    floor 等范围检查全部假绿,问题拖到 CI 才暴露。在 main 自身或没有
    origin/main 时退回未推送范围。"""
    branch = _git("rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch != "main":
        try:
            _git("rev-parse", "--verify", "origin/main")
        except subprocess.CalledProcessError:
            pass
        else:
            return "origin/main...HEAD"
    return _unpushed_range()


def check_no_ai_attribution(rng: str | None) -> tuple[bool, str]:
    # Fallback without a remote branch: last 10 commits, but never commits
    # already on origin/main — a merge from main would otherwise drag
    # third-party trailers (e.g. dependabot's Co-authored-by) into the scan.
    rng = rng or "HEAD~10..HEAD"
    body = _git("log", "--format=%B", rng, "--not", "origin/main").lower()
    hits = [t for t in FORBIDDEN_TRAILERS if t in body]
    if hits:
        return False, f"commit 信息含禁止的署名字样: {hits}(范围 {rng})"
    return True, f"无 AI 署名(范围 {rng})"


def check_clean_worktree() -> tuple[bool, str]:
    dirty = _git("status", "--porcelain").strip()
    if dirty:
        return False, "工作区不干净:\n" + dirty
    return True, "工作区干净"


def check_report_committed(rng: str | None) -> tuple[bool, str]:
    if rng is None:
        return True, "无远端分支,跳过报告落盘检查"
    files = _git("diff", "--name-only", rng).splitlines()
    touched_code = any(f.startswith(("src/", "tests/")) for f in files)
    has_report = any(
        f.startswith("docs/reports/") and f != "docs/reports/TEMPLATE.md" for f in files
    )
    if touched_code and not has_report:
        return False, f"未推送 commit 改了 src/tests 但 docs/reports/ 无新报告(范围 {rng})"
    if touched_code:
        return True, "代码改动已附带落盘报告"
    return True, "本批无 src/tests 改动,不要求报告"


def check_report_has_workflow_output(rng: str | None) -> tuple[bool, str]:
    """批次报告必须粘贴 check_workflow 自身输出(CLAUDE.md §7),不收占位句。"""
    if rng is None:
        return True, "无远端分支,跳过报告输出检查"
    files = _git("diff", "--name-only", rng).splitlines()
    reports = [
        f for f in files
        if f.startswith("docs/reports/") and f != "docs/reports/TEMPLATE.md"
    ]
    missing: list[str] = []
    for f in reports:
        try:
            text = Path(f).read_text(encoding="utf-8")
        except OSError:
            continue  # 报告被删/改名,落盘检查已覆盖存在性
        if "check_workflow" not in text or not re.search(r"\[(?:PASS|FAIL)\]", text):
            missing.append(f)
    if missing:
        return False, "报告未粘贴 check_workflow 输出([PASS]/[FAIL] 行): " + ", ".join(missing)
    if reports:
        return True, "报告含 check_workflow 输出"
    return True, "本批无新报告,不检查输出"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--range", dest="rng", default=None, help="要核对的 rev 范围")
    args = parser.parse_args()
    rng = args.rng if args.rng else _unpushed_range()
    checks = [
        ("AI 署名", check_no_ai_attribution(rng)),
        ("工作区", check_clean_worktree()),
        ("报告落盘", check_report_committed(rng)),
        ("报告含验证输出", check_report_has_workflow_output(rng)),
        ("floor", check_floor(rng)),
        ("前端锁文件", check_frontend_lock(rng)),
    ]
    # Windows 默认 cp1252 无法打印中文检查名,统一切 UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    failed = False
    for name, (ok, msg) in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {msg}")
        failed |= not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
