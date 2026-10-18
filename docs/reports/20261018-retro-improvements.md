# 批次结果报告:retro-improvements(2026-10-18)

## 批准依据

> 用户对 /retro 五项候选答复:「五点都改」。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 测试隔离:T2S_EXAMPLES_PATH 重定向临时目录,全量 pytest 不再改写 config/t2s_examples.json | tests/conftest.py | 本提交 |
| 高 | 守卫:external manifest 必须存在 frontend/<name>/ workspace(datacompare 挂载落空的机械防复发) | tests/test_registry.py | 本提交 |
| 中 | CLAUDE.md:§4 Evidence-First 9 条压缩为 3 条;§8 增"编排票级定向测试"与"ui --build"两行 | CLAUDE.md | 本提交 |
| 低 | 迁移文档增"先例速查"(聊天/表单两类页先例、i18n parity 测试模式、截图脚本、拆票法) | docs/react_migration.md | 本提交 |

## 验证结果

```
ruff check src tests          -> All checks passed!
mypy                          -> Success: no issues found in 114 source files
pytest -q                     -> 3129 passed, 1 skipped, 88 deselected in 171.97s
git status config/t2s_examples.json(全量 pytest 后) -> 无改动(漂移根治生效)
pytest tests/test_registry.py -> 27 passed(含新守卫)
python scripts/check_workflow.py -> 三项 PASS(本提交后)
```

## 前后差异

- 测试:3128 → 3129(+1 守卫测试);全量 pytest 后工作区首次保持干净(此前每次漂移)。
- 文档:CLAUDE.md §4 由 15 行减至 3 行;react_migration.md +18 行先例速查。

## 遗留问题清单

| 问题 | 证据 | 原因 | 影响 | 优先级 | 建议 |
| --- | --- | --- | --- | --- | --- |
| uitest engine 残留已退役页引用与孤儿布局 CSS | 20261018-datacompare 报告遗留清单 | 逐页迁移遗留 | 死代码 | 低 | 专项清理批次 |
