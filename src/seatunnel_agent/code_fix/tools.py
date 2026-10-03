# -*- coding: utf-8 -*-
"""Code-fix agent tools — all bound to one working directory.

Every path is resolved and must stay under the workdir (``.git`` excluded);
``apply_patch`` is exact-unique-string replacement so the model can never
clobber a file it has not read precisely.  No git tools, no shell tool —
the agent edits files and runs pytest, nothing else.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ..agent_core import ToolSpec

_READ_MAX_LINES = 400
_OUTPUT_TAIL = 6000


def _resolve(workdir: Path, rel: str) -> Path:
    p = (workdir / rel).resolve()
    try:
        p.relative_to(workdir.resolve())
    except ValueError:
        raise ValueError(f"path escapes the working directory: {rel}")
    if ".git" in p.parts:
        raise ValueError("the .git directory is off limits")
    return p


def run_pytest(workdir: Path, selector: str = "") -> str:
    """Run the tests; output = exit code + tail of combined output."""
    cmd = [sys.executable, "-m", "pytest", "-x", "-q", "--no-header",
           "-p", "no:cacheprovider"]
    if (selector or "").strip():
        cmd.append(selector.strip())
    proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300)
    out = (proc.stdout or "") + (proc.stderr or "")
    if len(out) > _OUTPUT_TAIL:
        out = "…(truncated)\n" + out[-_OUTPUT_TAIL:]
    status = "GREEN" if proc.returncode == 0 else f"EXIT {proc.returncode}"
    return f"[{status}]\n{out}"


def build_tools(workdir: Path) -> list[ToolSpec]:
    workdir = Path(workdir)

    def run_tests(selector: str = "") -> str:
        return run_pytest(workdir, selector)

    def list_files(pattern: str = "**/*.py") -> str:
        hits = [str(p.relative_to(workdir)) for p in
                sorted(workdir.glob(pattern))
                if p.is_file() and ".git" not in p.parts][:200]
        return "\n".join(hits) or "(no match)"

    def read_file(path: str, start: int = 1, end: int = 200) -> str:
        p = _resolve(workdir, path)
        lines = p.read_text(encoding="utf-8",
                            errors="replace").splitlines()
        start = max(1, int(start))
        end = min(len(lines), max(start, int(end)), start + _READ_MAX_LINES)
        return "\n".join(f"{i}\t{lines[i - 1]}"
                         for i in range(start, end + 1)) or "(empty)"

    def apply_patch(path: str, old: str, new: str) -> str:
        p = _resolve(workdir, path)
        text = p.read_text(encoding="utf-8")
        n = text.count(old)
        if not old:
            return "ERROR: old must not be empty"
        if n == 0:
            return "ERROR: old string not found — read the file again"
        if n > 1:
            return f"ERROR: old string occurs {n} times — make it unique"
        p.write_text(text.replace(old, new), encoding="utf-8",
                     newline="\n")
        return f"patched {path}"

    s = {"type": "string"}
    return [
        ToolSpec("run_tests", "运行 pytest(-x -q)。selector 可指定文件/"
                 "用例,留空跑全部。返回退出状态与输出尾部。",
                 {"type": "object", "properties": {"selector": s},
                  "required": []}, run_tests),
        ToolSpec("list_files", "列出匹配 glob 的文件(相对路径,最多 200 个)。",
                 {"type": "object", "properties": {"pattern": s},
                  "required": []}, list_files),
        ToolSpec("read_file", "读取文件内容(带行号;start/end 为行号)。",
                 {"type": "object",
                  "properties": {"path": s,
                                 "start": {"type": "integer"},
                                 "end": {"type": "integer"}},
                  "required": ["path"]}, read_file),
        ToolSpec("apply_patch", "把文件中唯一出现的 old 精确替换为 new。"
                 "old 必须与文件内容逐字符一致且只出现一次。",
                 {"type": "object",
                  "properties": {"path": s, "old": s, "new": s},
                  "required": ["path", "old", "new"]}, apply_patch),
    ]
