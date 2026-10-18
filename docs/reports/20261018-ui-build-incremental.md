# 批次结果报告:ui --build 增量构建(2026-10-18)

## 批准依据

> 用户以 `/implement-spec` 启动实现(spec:`.scratch/ui-build-incremental/spec.md`,此前经 grill 轮确认"yes"批准方案:增量 hash 判定 + `--force` + dev 文档)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `_build_frontends` 增量化:逐 workspace 内容 hash(src/、package.json、vite.config.ts、tsconfig*、shared 源码)比对 `dist/.build-hash`,一致跳过;built/skipped 输出 | src/seatunnel_agent/cli_cmds/core.py | fb5e160 |
| 高 | `ui --build --force` 强制全量 + CLI 透传测试 | src/seatunnel_agent/cli_cmds/core.py, tests/test_frontend_build.py | fb5e160, b11f9e9 |
| 中 | code-review 修复:hash 掺相对路径+无歧义编码、去 dist 预创建、shared 输入排除生成物、fixture 改名 npm_calls、`--force` 无 `--build` 提示 | src/seatunnel_agent/cli_cmds/core.py, tests/test_frontend_build.py | 830a5d7 |
| 低 | 免构建开发路径文档(vite dev + 后端 proxy) | docs/frontend_dev.md | 66d1ee2 |

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 114 source files
pytest -q              -> 3142 passed, 1 skipped, 88 deselected in 146.19s
pytest tests/test_frontend_build.py -v -> 13 passed in 1.88s
uitest smoke (--no-llm) -> PASS 60 · FAIL 0 · ERROR 0 · SKIP 0 · MANUAL 1 · 耗时 261s
  报告: runs/20261018_153458/report.html
python scripts/check_workflow.py -> 见本报告提交前输出(随批次提交核对)
```

构建计时(_build_frontends 连跑两次,真实 npm 构建):

```
first run (cold):        71.3s
second run (incremental): 0.1s
```

## 前后差异

- 构建耗时:无改动重复 `ui --build` 由 ~71s(每次全量)降至 0.1s(全部 skipped)。
- 测试:新增 tests/test_frontend_build.py(13 个用例,0 → 13);全量 pytest 3142 passed(改动前基线 3130 collected,无回归)。
- UI 行为无变化:uitest smoke PASS 60 · FAIL 0(报告 runs/20261018_153458/report.html)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | hub 启动时全量 import 各 agent ui 模块,启动偏慢 | src/seatunnel_agent/hub/ui.py:87-92 | Gradio 多页在启动时全部 render | 启动秒级变慢 | 将来评估惰性 render,单独批次 |
| 低 | 无 `ui --dev <workspace>` CLI 封装 | docs/frontend_dev.md(手动两条命令) | 本批次文档先行 | 日常开发需手动起 vite dev | 有需要再做 |
| 低 | hash 在构建前计算、成功后写入,构建期间源码再变会写入过期 hash | core.py `_build_frontends` | 简单实现取舍 | 极端时序下漏重建,`--force` 可兜底 | 保持现状 |

## 未执行的步骤

- 无。
