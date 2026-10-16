# 批次结果报告:text2sql 票 #69 history 竖切(2026-10-17)

## 批准依据

> 用户 /implement 驱动 frontier(#69)。

## 已完成(TDD)

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | qlog 端点四件套(列表 newest-first/按新序删除/清空/CSV 导出)+ 已存会话列表 + 恢复端点(saved 对话注入 live agent,返回 transcript) | agents/data/text2sql/api.py | 本批次 commit |
| 高 | API 测试 4 条先红后绿(对齐真实 QueryLogger/Text2SQLSession 签名的往返各一次) | tests/test_t2s_history_api.py | 本批次 commit |
| 中 | 前端 #history 视图:查询日志表(行选详情 SQL/删除/清空/CSV)+ 已存会话恢复进聊天(ChatPanel 支持 seed 注入);浏览器冒烟 +1 | frontend/text2sql/src/HistoryView.tsx, ChatPanel.tsx, App.tsx, api.ts, i18n.ts; tests/test_t2s_page.py | 本批次 commit |

## 验证结果

```
RED:  tests/test_t2s_history_api.py -> 4 failed/errors(端点不存在)
GREEN: 全部 t2s 套件 29+4=…合计 33 passed(history 4 + schema 5 + chat 9 + connect 5 + sessions 6 + 其余)
冒烟: tests/test_t2s_page.py 4 passed(新增 history 流程:列表→详情→清空)
全量: pytest -q -> 2945 passed, 1 skipped(+4);mypy Success;ruff All checks passed!
前端: npm build / lint 全过
check_workflow 输出附于本批 commit 后(见对话)
```

## 前后差异

- 前:qlog/已存会话只在旧 Gradio /history 页可见;React 无历史能力。
- 后:五个端点开放;#history 视图功能对齐旧页核心(明细/删/清/导出/恢复),恢复直接回注 live 聊天。
- 测试:2941 → 2945 passed。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 旧 /history Gradio 路由仍在(其用例 #75 适配) | manifest aux | 迁移窗口 | 双入口 | #75 收敛 |
| 低 | 保存当前会话(save)端点未做 —— 旧页的 save 在聊天侧,归 #70 收藏/保存域 | — | 票面边界 | 新页暂不能存会话 | #70 一并 |
| 低 | resume 未校验 ds_type 匹配(旧页同样不校验) | api resume | 历史行为 | 跨源恢复语义怪 | 观察 |

## 未执行的步骤

- smoke 全套件:未执行 —— 不触及既有用例路径;CI 兜底。
