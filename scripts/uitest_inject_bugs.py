# -*- coding: utf-8 -*-
"""Acceptance criterion #2: inject three bug classes; each must be caught.

① frontend wiring: connect A outputs routed to B's status/table components
② backend crash: drop the (host or "") None-guard for hidden textboxes
③ i18n drift: change the port-error message text

For each: patch source, run the covering case(s) via the CLI, expect a
non-zero exit (FAIL/ERROR), restore, and finally confirm the suite is green
again on the untouched tree.
"""
import io
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

UI = Path("src/seatunnel_agent/data_comparison_ui.py")
I18N = Path("src/seatunnel_agent/data_comparison/i18n.py")

BUGS = [
    ("① 前端接错组件: 连接A的输出接到B侧组件",
     UI,
     "        outputs=[status_a, table_a, host_a, port_a, db_a],",
     "        outputs=[status_b, table_b, host_a, port_a, db_a],",
     ["X4"]),
    ("② 后端崩溃: 去掉隐藏 auth 组件的 None 守卫",
     UI,
     '        u = (username or "").strip() or None',
     "        u = username.strip() or None",
     ["A4"]),
    ("③ i18n 文案漂移: 改掉端口错误提示",
     I18N,
     '        "dc_port_not_number": "端口号必须是数字",',
     '        "dc_port_not_number": "端口格式错误",',
     ["A4"]),
]


def run_cases(ids):
    cmd = [sys.executable, "-m", "seatunnel_agent.ui_testing", "run",
           "--no-llm", "--case", *ids]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


failures = []
for title, path, old, new, case_ids in BUGS:
    src = path.read_text(encoding="utf-8")
    assert old in src, f"patch anchor missing for {title}"
    path.write_text(src.replace(old, new), encoding="utf-8", newline="")
    try:
        code, out = run_cases(case_ids)
        tail = "\n".join(out.splitlines()[-8:])
        caught = code != 0
        print(f"{'✅ 抓到' if caught else '❌ 漏过'} — {title}")
        print("    " + "\n    ".join(tail.splitlines()[-4:]))
        if not caught:
            failures.append(title)
    finally:
        path.write_text(src, encoding="utf-8", newline="")

# ④ self-healing: rename a button label; WITH an LLM the run must heal the
# lookup (verdict HEALED, exit 0) and emit a paste-ready LABELS patch.
print()
print("④ 自愈闭环: 注入按钮文案漂移(结构对比→结构比对),期望 HEALED…")
import os                                    # noqa: E402
from dotenv import load_dotenv               # noqa: E402
load_dotenv()
if not (os.getenv("API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
    print("   ⏭️ 跳过: 未配置 API_KEY(自愈需要 LLM)")
else:
    heal_old = '"dc_compare_schema": "结构对比",'
    heal_new = '"dc_compare_schema": "结构比对",'
    src = I18N.read_text(encoding="utf-8")
    assert heal_old in src, "heal patch anchor missing"
    I18N.write_text(src.replace(heal_old, heal_new), encoding="utf-8",
                    newline="")
    try:
        cmd = [sys.executable, "-m", "seatunnel_agent.ui_testing", "run",
               "--case", "C1"]                       # WITH LLM on purpose
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
        out = (r.stdout or "") + (r.stderr or "")
        healed = r.returncode == 0 and "HEALED" in out
        print(f"{'✅ 自愈成功' if healed else '❌ 未自愈'}")
        print("    " + "\n    ".join(out.splitlines()[-5:]))
        if not healed:
            failures.append("④ 自愈闭环未生效")
        elif "labels_patch" not in out and "LABELS" not in out:
            failures.append("④ 自愈成功但未输出 LABELS 补丁")
    finally:
        I18N.write_text(src, encoding="utf-8", newline="")

print()
print("回归确认: 注入全部还原后重跑覆盖用例…")
code, out = run_cases(["X4", "A4"])
print("\n".join(out.splitlines()[-6:]))
if code != 0:
    failures.append("还原后用例未恢复绿色")

print()
if failures:
    print("验收未通过:", failures)
    sys.exit(1)
print("验收通过: 三类注入 bug 全部被抓到,还原后恢复绿色。")
