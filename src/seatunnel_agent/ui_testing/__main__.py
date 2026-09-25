"""CLI entry point.

    python -m seatunnel_agent.ui_testing run [--suite smoke] [--case A5 B3]
        [--headed] [--port 7912] [--no-llm] [--keep-app] [--base-url URL]
    python -m seatunnel_agent.ui_testing list [--suite full]
"""

from __future__ import annotations

import argparse
import io
import sys


def _utf8_stdout() -> None:
    # Windows consoles default to GBK; the reports/labels are Chinese.
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                      errors="replace")


def cmd_run(args: argparse.Namespace) -> int:
    from .report import print_summary, write_html, write_json
    from .runner import run_suite

    def progress(i: int, n: int, cr) -> None:
        mark = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥",
                "SKIP": "⏭️"}.get(cr.verdict, "?")
        print(f"[{i}/{n}] {mark} {cr.verdict:<5} {cr.case_id:<5} "
              f"{cr.title} ({cr.elapsed_ms / 1000:.1f}s)", flush=True)

    repeat = max(1, getattr(args, "repeat", 1))
    signatures: list[dict[str, str]] = []
    rc = 0
    for round_no in range(1, repeat + 1):
        if repeat > 1:
            print(f"—— 第 {round_no}/{repeat} 轮 ——", flush=True)
        rr, run_dir = run_suite(
            suite=args.suite,
            case_ids=args.case or None,
            headed=args.headed,
            port=args.port,
            no_llm=args.no_llm,
            keep_app=args.keep_app,
            base_url=args.base_url,
            on_progress=progress,
        )
        write_json(rr, run_dir)
        html_path = write_html(rr, run_dir)
        print_summary(rr)
        print(f"\n报告: {html_path.resolve()}")
        counts = rr.counts()
        if counts["FAIL"] or counts["ERROR"]:
            rc = 1
        signatures.append({c.case_id: c.verdict for c in rr.cases})

    if repeat > 1:
        flaky = sorted({cid for sig in signatures for cid in sig
                        if len({s.get(cid) for s in signatures}) > 1})
        if flaky:
            print(f"\n⚠️ FLAKY ({len(flaky)}):")
            for cid in flaky:
                seq = " → ".join(s.get(cid, "-") for s in signatures)
                print(f"  {cid}: {seq}")
            rc = 1
        else:
            print(f"\n{repeat} 轮 verdict 完全一致,零 flaky。")
    return rc


def cmd_compare(args: argparse.Namespace) -> int:
    from .rundiff import RUNS_DIR, diff_runs, format_diff, list_runs

    if args.runs:
        if len(args.runs) != 2:
            print("用法: compare <旧运行> <新运行>")
            return 2
        old_dir, new_dir = (RUNS_DIR / r for r in args.runs)
    else:
        runs = list_runs()
        if len(runs) < 2:
            print("runs/ 下不足两轮运行")
            return 1
        old_dir, new_dir = runs[-2], runs[-1]
    d = diff_runs(old_dir, new_dir)
    print(format_diff(d))
    return 1 if d.regressions else 0


def cmd_list(args: argparse.Namespace) -> int:
    from .loader import filter_cases, load_cases

    cases = load_cases()
    if getattr(args, "coverage", False):
        from .coverage import compute_coverage
        cov = compute_coverage(cases)
        if cov is None:
            print("未找到 examples/dc_test_checklist.html")
            return 1
        counts = cov.counts()
        label = {"auto": "已自动化", "runner": "框架内置",
                 "manual": "人工用例", "missing": "未覆盖"}
        for status in ("auto", "runner", "manual", "missing"):
            ids = [r.item_id for r in cov.rows if r.status == status]
            print(f"{label[status]} ({len(ids)}): {' '.join(ids)}")
        if cov.extra_case_ids:
            print(f"清单之外 ({len(cov.extra_case_ids)}): "
                  f"{' '.join(cov.extra_case_ids)}")
        total = len(cov.rows)
        done = counts["auto"] + counts["runner"] + counts["manual"]
        print(f"\n{total} 项清单中 {done} 项已闭环 "
              f"(自动化 {counts['auto']} + 框架 {counts['runner']} + "
              f"人工标注 {counts['manual']}), 未覆盖 {counts['missing']}")
        return 0
    if args.suite:
        shown = filter_cases(cases, args.suite)
    else:
        shown = cases
    for c in shown:
        ai_n = sum(1 for s in [*c.setup, *c.steps] if s.ai)
        ai_j = sum(1 for a in c.expect if a.kind == "ai_judge")
        extra = []
        if ai_n:
            extra.append(f"{ai_n} ai-step")
        if ai_j:
            extra.append(f"{ai_j} ai-judge")
        tag = ",".join(c.tags)
        print(f"{c.id:<5} [{tag:<14}] {c.title}"
              + (f"  ({', '.join(extra)})" if extra else ""))
    print(f"\n{len(shown)} case(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    p = argparse.ArgumentParser(prog="python -m seatunnel_agent.ui_testing",
                                description="UI 测试 Agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="运行用例")
    pr.add_argument("--suite", default="smoke",
                    choices=["smoke", "full", "hive", "slow", "sqlite"],
                    help="按标签选套件 (默认 smoke)")
    pr.add_argument("--case", nargs="*", default=[],
                    help="指定用例 id (优先于 --suite)")
    pr.add_argument("--headed", action="store_true", help="有头浏览器调试")
    pr.add_argument("--port", type=int, default=7912,
                    help="被测应用端口 (默认 7912, 严禁 7860)")
    pr.add_argument("--no-llm", action="store_true",
                    help="跳过 ai:/ai_judge 用例, 零 token 极速回归")
    pr.add_argument("--keep-app", action="store_true",
                    help="结束后不杀被测应用 (连续调试)")
    pr.add_argument("--base-url", default="",
                    help="复用已启动的应用而非自起子进程")
    pr.add_argument("--repeat", type=int, default=1,
                    help="连续跑 N 轮并比对 verdict, 不一致标 FLAKY 并退出非零")
    pr.set_defaults(fn=cmd_run)

    pc = sub.add_parser("compare", help="对比两轮运行的 verdict 变化")
    pc.add_argument("runs", nargs="*", default=[],
                    help="两个 runs/<ts> 目录名; 缺省取最近两轮")
    pc.set_defaults(fn=cmd_compare)

    pl = sub.add_parser("list", help="列出用例")
    pl.add_argument("--suite", default="", help="只列出该套件")
    pl.add_argument("--coverage", action="store_true",
                    help="显示人工清单覆盖对照")
    pl.set_defaults(fn=cmd_list)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
