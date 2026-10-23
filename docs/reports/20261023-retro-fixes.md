# 批次结果报告:retro 环境修复(2–5)(2026-10-23)

## 批准依据

> 用户:"把其他retro的也给fix"(retro 清单 2/3/4/5;1 号 heredoc hook 已单独完成于全局 ~/.claude,不入库)。

## 已完成

| # | 内容 | 文件 |
| --- | --- | --- |
| 2 | scripts/ 纳入 lint:存量 6 条 ruff 告警 `--fix` 清零;CI(lint.yml)与 CLAUDE.md 第 8 节命令改为 `ruff check src tests scripts` | scripts/seed_hive.py、scripts/uitest_flaky_check.py、scripts/uitest_inject_bugs.py、.github/workflows/lint.yml、CLAUDE.md |
| 3 | CLAUDE.md 瘦身 98→84 行:worktree 事故 30 行叙事移入 docs/pitfalls.md(新章节),CLAUDE.md 第 9 节保留 4 条合并后的固化规则 + 指针 | CLAUDE.md、docs/pitfalls.md |
| 4 | ui_testing loader 阈值断言(≥18/≥16 魔法数)改为与 YAML 源逐一对账(`len(cases) == len(raw_yaml)`,smoke 同理);退役用例的 diff 从此必然触碰断言来源 | tests/test_ui_testing.py |
| 5 | `make_page_url` 新增 `dummy_llm_key=True` 便捷参数(docstring 说明场景与先例),test_t2s_page.py 改用之 | tests/conftest.py、tests/test_t2s_page.py |

## 验证结果

```
ruff check src tests scripts        -> All checks passed!(scripts 为新增范围)
mypy                                -> Success: no issues found in 107 source files
pytest tests/test_ui_testing.py -q  -> 62 passed(派生断言替换魔法数)
pytest -q(全量)                   -> 3347 passed, 1 skipped, 242 deselected
pytest tests/test_t2s_page.py -m uitest -> 18 passed(dummy_llm_key 参数生效)
python scripts/check_workflow.py    -> 本报告提交后复跑,见对话
```

UI 未改动,未跑 uitest smoke(改动为 lint 范围/文档/测试断言/测试 fixture)。

## 前后差异

- lint 盲区:scripts/ 6 条存量告警 → 0,且 CI 永久看护。
- CLAUDE.md:98 行 → 84 行(每轮上下文少付约 15 行,规则语义不变,叙事在 pitfalls.md 可溯)。
- loader 断言:两个手工同步的魔法数 → 与 YAML 源自动对账(该类失误已发生 2 次,现结构性消除)。
- 页面测试假 key:埋在 t2s 文件注释里的修法 → conftest 具名参数,下一个页面可发现复用。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- retro 第 1 条(heredoc hook):本批未动——已于早前作为全局配置完成(~/.claude/hooks/block_heredoc.py + settings.json,本会话已实测双向拦截/放行,且在 ship 批次真实拦截两次)。
