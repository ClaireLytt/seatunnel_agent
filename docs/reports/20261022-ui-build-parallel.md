# 批次结果报告:ui-build-parallel(2026-10-22)

## 批准依据

> 用户经 /grill-me 确认方案(Q1–Q6 回复 "yes")后依次调用 /to-spec、/to-tickets、/implement-spec 启动实现。spec:.scratch/ui-build-parallel/spec.md;票:.scratch/ui-build-parallel/issues/01–03。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 并行构建核心:_build_frontends 有界线程池(默认 min(CPU,6))、失败汇总、失败者不写 .build-hash | src/seatunnel_agent/cli_cmds/core.py, tests/test_frontend_build.py | 3973f30 |
| 中 | ui --build --jobs 参数 + 构建统计行(built/skipped/failed + 耗时) | src/seatunnel_agent/cli_cmds/core.py, tests/test_frontend_build.py | 7a78d45 |
| 中 | CI lint 扩展到全部 25 个前端 workspace(单 job) | .github/workflows/lint.yml | 461ece2 |
| 中 | code-review 修复:统计准确性(无 dist 不计 built)、--jobs IntRange(min=1)+钳制、日志措辞、测试结构清理 | src/seatunnel_agent/cli_cmds/core.py, tests/test_frontend_build.py | afb9cdc |

分支:feat/ui-build-parallel(自 main 63261c8 切出)。

## 验证结果

```
ruff check src tests                      -> All checks passed!
mypy                                      -> Success: no issues found in 109 source files
pytest -q(全量,worktree t02,首跑)       -> 1 failed, 3304 passed, 1 skipped, 239 deselected(失败为既有顺序 flake,见遗留)
pytest -q(全量,复跑)                     -> 3305 passed, 1 skipped, 239 deselected, 2 warnings in 147.80s
pytest tests/test_frontend_build.py -v    -> 27 passed in 3.45s
npm run lint --workspaces --if-present    -> EXIT=0,全部 workspace 通过(票 03 子代理于 t03 worktree 执行)
```

UI 改动:无前端页面改动(仅构建流程与 CI),未跑 uitest(见"未执行的步骤")。

## 前后差异

- 测试类:tests/test_frontend_build.py 13 → 27 个用例(+14:并发上限、失败汇总、哈希写入语义、jobs 钳制、统计行等),全部通过。
- 性能(真机,25 workspace,force 全量重建,票 02 子代理实测):
  - 并行(jobs=6):104.9s(`frontend build: 25 built, 0 skipped, 0 failed in 104.9s`)
  - 串行(jobs=1):331.6s
  - 加速比 ≈ 3.2x。
- CI lint 覆盖:1 个 workspace(uitest)→ 25 个 workspace。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 既有顺序相关 flake:test_ui_testing.py::TestLoader::test_builtin_cases_load 全量首跑失败、单跑/复跑均过 | 首跑 `1 failed, 3304 passed`;复跑 `3305 passed`;单测 `1 passed`(dev 与 worktree 均过) | 测试间状态污染(与本批次 diff 无关,diff 未触及 ui_testing) | 偶发 CI 红 | 单独排查污染源(二分测试顺序) |
| 低 | jobs=1 时输出由流式变为构建完成后整块刷出 | core.py 并行路径 capture_output | 统一走捕获+前缀刷出路径,实现简单 | 长构建期间无实时输出 | 如有需要再为 jobs=1 恢复流式 |
| 低 | 失败构建的 stdout/stderr 拼接展示,丢失交错顺序 | core.py `proc.stdout + proc.stderr` | capture_output 分流捕获 | 排障时顺序信息缺失 | 需要时改用合并流(stderr→stdout) |
| 低 | npm --workspaces lint 遇首个失败 workspace 即停,单次 CI 未必暴露全部 lint 错误 | npm workspaces 顺序执行语义 | npm 行为 | 多 workspace 同时坏时需多轮修复 | 可接受;必要时换循环+continue-on-error 汇总 |

## 未执行的步骤

- uitest smoke:未执行。本批次无前端页面/UI 改动(仅 Python 构建逻辑与 CI workflow),按 CLAUDE.md §8 不要求。
- `seatunnel-agent ui --build` 页面级验证:未以 hub 启动形态执行;等效验证为票 02 真机全量构建两轮(104.9s / 331.6s,25 built 0 failed)。
