# 批次结果报告:SQL Review 迁移评审修复 + retro 环境改进(2026-10-17)

## 批准依据

> 用户:"① code-review 修复项（上面 1+5 条）② retro 环境改进（前 6 条）。完成"

## 已完成

### ① code-review 修复(Standards 硬违规 1 + Spec 5)

| 优先级 | 内容 | 文件 |
| --- | --- | --- |
| 高 | 硬违规:9125b51 混入的 config/t2s_examples.json 运行时噪音还原为迁移前内容(docs/pitfalls.md 那行为用户自己的既有编辑,保留) | config/t2s_examples.json |
| 高 | Spec1:/review 增 `source: Literal["api","ui"]`,React 页回传 "ui",审查日志来源语义恢复;另把 FixRequest.mode 收紧为 Literal(顺带消掉评审提的 Primitive Obsession) | api.py、api.ts、App.tsx |
| 中 | Spec2:?dialect= 支持别名(pg/postgres/odps/mssql/tsql/ck/…,镜像 linter._DIALECT_ALIASES) | api.ts、App.tsx |
| 中 | Spec3:规则非 mapping 时给出诊断信息("rules must be a YAML mapping"),不再回显输入片段 | App.tsx |
| 高 | Spec4:static fix"无可修复"改为按 HTTP 422 状态码分支(新增 ApiError 带 status),不再匹配英文 detail 文案 | api.ts、App.tsx |
| 中 | Spec5:Clear 恢复旧页行为——保留 DDL/规则,只清 SQL/报告/修复结果,并加注释说明 | App.tsx |
| 中 | 新增 API 测试:source 合法值 200 / 非法值 422 | tests/test_sql_review.py |

### ② retro 环境改进(6 条)

| # | 内容 | 文件 |
| --- | --- | --- |
| 1 | 删除指向不存在 tools/ui_check_hook.py 的 PostToolUse hook(每次 Write/Edit 报错的噪音源) | .claude/settings.json |
| 2 | 新增 Gradio→React 迁移触点清单文档 + CLAUDE.md §2 导航指针 | docs/react_migration.md、CLAUDE.md |
| 3 | coverage 测试改结构性断言(不再钉死具体用例 id) | tests/test_ui_testing.py |
| 4 | settings env 加 PYTHONUTF8=1;pitfalls 追加 cp1252 编码条目(本日第 3 次命中) | .claude/settings.json、docs/pitfalls.md |
| 5 | ccmetr 启动器 python3 缺失时回退 python | .claude/ccmetr/bin/ccmetr |
| 6 | CLAUDE.md §8 增加前端 lint/build 验证命令 | CLAUDE.md |

## 验证结果

```
npm run lint --workspace sql_review       -> eslint src(无输出,通过)
npm run build --workspace sql_review      -> ✓ built in 18.99s
ruff check src tests                      -> All checks passed!
mypy                                      -> Success: no issues found in 103 source files
pytest -q                                 -> 2976 passed, 1 skipped, 99 deselected
pytest -m uitest tests/test_sql_review_page.py -> 4 passed
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                                          -> (见下方补记)
python scripts/check_workflow.py          -> (见下方补记)
```

## 前后差异

- 测试:sql_review+ui_testing 组 375 → 376 passed(新增 source 测试,coverage 断言改写);全量 2975 → 2976。
- 行为:?dialect=pg 现在落到 PostgreSQL(此前静默停在 Hive);Clear 不再清 DDL/规则;static fix 提示对后端文案变更免疫;审查日志可再按 ui/api 区分。
- 环境:写文件不再触发 hook 报错;控制台默认 UTF-8。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | DIALECTS/DIALECT_NAMES/CHECK_CATALOG_EN/别名表仍为前后端双份(评审 judgement call,未列入本批圈选) | api.ts、i18n.ts vs prompts.py、linter.py、i18n.py | 避免为此新增 meta 端点的范围扩张 | 新增方言/类别需双端同改 | 后续如加 meta 端点时一并收敛 |
| 低 | localStorage 桥键名裸串散布 4 文件(同上,未圈选) | App.tsx、sql_transpile/ui.py:220 等 | 对端仍是 Gradio,收敛点不明 | 改键名需全局搜 | 对端迁 React 时定义共享常量 |
| 低 | /transpile、/dataskew 仍为 Gradio | manifest | 不在范围 | 风格不一致延续 | 按 docs/react_migration.md 迁移 |

## 未执行的步骤

- 无(uitest smoke 与 check_workflow 结果在本报告提交批次中补记于对话;若 smoke FAIL 本批不标记完成)。
