# 批次结果报告:text2sql 票 #68 schema 竖切(2026-10-17)

## 批准依据

> 用户 "yes" 接受继续 frontier(#68);/implement 流程。

## 已完成(TDD)

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | schema 端点四件套:列表(列数/备注)、表详情(列/类型/分区)、过滤(narrow/widen,全量快照为 widen 源,未知表 400)、重载(刷新快照);替换旧 /schema 桩的职责 | agents/data/text2sql/api.py | 本批次 commit |
| 高 | SessionEntry 增 extras 快照袋(replace_agent 原子保留);_build_agent 析出 _agent_from_store 供过滤复用 | sessions.py, api.py | 本批次 commit |
| 高 | API 测试 5 条先红(4 failed)后绿(列表/详情+404/过滤窄宽+400/重载/未知会话) | tests/test_t2s_schema_api.py | 本批次 commit |
| 中 | 前端:侧栏表过滤面板(搜索/勾选/全选清空/应用/⟳重载)+ #schema 哈希视图(表列表→列详情卡);浏览器冒烟 +1(真 SQLite 全链路:narrow 1/2 → schema 视图列详情) | frontend/text2sql/src/SchemaPanel.tsx, SchemaBrowser.tsx, App.tsx, api.ts, i18n.ts; tests/test_t2s_page.py | 本批次 commit |

## 验证结果

```
RED:  tests/test_t2s_schema_api.py -> 4 failed(端点不存在)
GREEN: schema 5 + sessions 6 + connect 5 + chat 9 = 25 passed(中途 ColumnSchema.dtype 命名修正)
冒烟: tests/test_t2s_page.py 3 passed(新增 schema 流程)
全量: pytest -q -> 2941 passed, 1 skipped(+5);mypy Success;ruff All checks passed!
前端: npm build / lint 全过
check_workflow 输出附于本批 commit 后(见对话)
```

## 前后差异

- 前:/schema API 是桩;表过滤只存在于旧 Gradio 页;React 页无 schema 能力。
- 后:四端点全功能;React 侧栏可过滤(窄/宽都行,快照兜底),#schema 视图替代旧 /schema-browser 的核心功能(旧路由仍在,#75 适配其用例)。
- 测试:2936 → 2941 passed。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 旧 /schema-browser Gradio 路由与 React #schema 视图并存 | manifest t2s aux | 该路由用例未适配(#75) | 双入口 | #75 收敛 |
| 低 | 过滤重建 agent 会丢当前对话上下文(与旧页行为一致) | _agent_from_store | 历史行为 | 过滤后对话重开 | 如需保留上下文另议 |

## 未执行的步骤

- smoke 全套件:未执行 —— 本票不触及既有用例路径;CI 兜底。
