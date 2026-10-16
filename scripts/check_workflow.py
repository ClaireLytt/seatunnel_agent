"""批次工作流机械核对(CLAUDE.md 第 7 节)。

检查项:
1. 未推送 commit 的提交信息中无 AI 署名(Co-Authored-By / Generated with)。
2. git 工作区干净(不允许留下未提交的修改)。
3. 未推送 commit 若改动了 src/ 或 tests/,docs/reports/ 中必须同批提交了新报告。

用法:python scripts/check_workflow.py [--range <rev-range>]
本地默认核对 origin/<当前分支>..HEAD;CI 中传 --range origin/<base>...HEAD 核对整个 PR。
任一项 FAIL 时退出码非 0,本批次不得标记完成。
"""

from __future__ import annotations

import argparse
import subprocess
import sys

FORBIDDEN_TRAILERS = ("co-authored-by", "generated with")


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


def check_no_ai_attribution(rng: str | None) -> tuple[bool, str]:
    rng = rng or "HEAD~10..HEAD"
    body = _git("log", "--format=%B", rng).lower()
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--range", dest="rng", default=None, help="要核对的 rev 范围")
    args = parser.parse_args()
    rng = args.rng if args.rng else _unpushed_range()
    checks = [
        ("AI 署名", check_no_ai_attribution(rng)),
        ("工作区", check_clean_worktree()),
        ("报告落盘", check_report_committed(rng)),
    ]
    failed = False
    for name, (ok, msg) in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {msg}")
        failed |= not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
