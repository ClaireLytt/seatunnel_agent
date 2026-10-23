# 批次结果报告:遗留修复(2026-10-23)

## 批准依据

> 用户:"都修复掉"(针对 20261023-tests-slim-down.md 遗留清单 4 条)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | ui_testing loader 下限 26/20 → 18/16(LGI 用例退役后同步) | tests/test_ui_testing.py | 1593a40 |
| 中 | check_workflow.py stdout 重配为 UTF-8,修复 Windows cp1252 崩溃 | scripts/check_workflow.py | 003cea3 |
| 中 | 提交用户批前的 lockfile 改动(devDeps 提升产物) | frontend/package-lock.json | 63e62dd |
| 低 | dev 推送远端 | — | 见验证结果 |

## 验证结果

```
ruff check src tests scripts/check_workflow.py -> All checks passed!
mypy                                  -> Success: no issues found in 106 source files
pytest tests/test_ui_testing.py -q    -> 62 passed in 4.50s
pytest -q(全量)                     -> 3331 passed, 1 skipped, 242 deselected in 140.83s
python scripts/check_workflow.py      -> 不加 PYTHONIOENCODING 直接运行,正常输出中文(见下)
```

UI 未改动,未跑 uitest。

## 前后差异

- 全量 pytest:2 failed, 3329 passed → **0 failed, 3331 passed**。
- check_workflow.py:裸跑 UnicodeEncodeError 崩溃 → 裸跑正常输出。
- git:dev 领先 origin 未推送 → 已推送(推送输出见对话)。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- uitest smoke:未执行(无 UI 改动)。
- scripts/ 其他文件的 6 条预存 ruff 告警(seed_hive.py、uitest_flaky_check.py、uitest_inject_bugs.py):未修(scripts/ 不在第 8 节 lint 范围,且非本批次范围)。
