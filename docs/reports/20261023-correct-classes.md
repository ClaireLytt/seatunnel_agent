# 批次结果报告:/correct 错误类机械化(2026-10-23)

## 批准依据

> 用户调用 `/correct` skill:把反复纠正的错误类固化到仓库,使下一个 agent 无法再犯。

## 错误类清单(≥2 次成类)与处置层级

| 类 | 证据(≥2 次) | 选择的层级 | 为何不是更高层级 |
| --- | --- | --- | --- |
| heredoc 损坏反斜杠/中文 | pitfalls 2026-10-15 + 本日 2 次返工 + ship 批次 2 次被拦 | 层级 2(全局 PreToolUse hook 硬拦,早前已装,本批登记) | 层级 1 需换 shell/OS,不可行 |
| 控制台 cp1252 UnicodeEncodeError | pitfalls 2026-10-17 记 3 次 + 本日 check_workflow 复发;pitfalls 声称 env 已配实则缺失(典型"规则无强制点"复发) | 层级 1(.claude/settings.json env `PYTHONUTF8=1`,环境消除) | — |
| 前端目录名 ≠ manifest.name | pitfalls 2026-10-18(datacompare/stale-dist 两例) | 层级 3(tests/test_registry.py 新约定测试) | 层级 1 需 registry 构建期扫 frontend/ 目录,把测试关切引入运行时,不值 |
| uitest 用例计数与 YAML 失同步 | 48c 退役漏改 + 本日修复(第 2 次) | 层级 3(派生断言,本日早批已落) | — |
| AI 署名 / 脏工作区 / 报告缺失 | pitfalls 2026-10-15 ×2 等 | 已有层级 2(check_workflow + CI),登记入表 | — |
| UI 改动未交用户验证 | pitfalls 2026-10-17(跨批次) | 层级 4(文档,CLAUDE.md §5)——判断型,无法机械判定"用户已验证" | 无可编写的检查 |

## 证明(新检查在真实旧错误上变红)

```
mv frontend/data_comparison frontend/datacompare
pytest …::test_external_manifest_names_match_frontend_workspace_dirs
  -> AssertionError: external manifests without frontend/<name>/ dir: ['data_comparison']
mv 还原 -> 1 passed
PYTHONUTF8=1 python scripts/check_workflow.py -> 中文输出正常(此前裸跑 UnicodeEncodeError)
```

## 验证结果

```
ruff check src tests scripts                    -> All checks passed!
pytest tests/test_registry.py tests/test_ui_testing.py -> 81 passed
pytest --collect-only -q                        -> 3349/3591 collected(+1 新约定测试)
python scripts/check_workflow.py                -> 三项 PASS(本报告提交后)
```

## 前后差异

- 规则↔强制点对照表落入 CLAUDE.md 第 10 节(10 条规则各自配强制点;唯一无强制点的 UI 验证规则被显式标注为判断型)。
- "写了规则没人执行"的缺口(PYTHONUTF8)被对照表模式当场抓出并补齐。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- uitest smoke:未执行(无 UI 改动)。
