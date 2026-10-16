# 批次结果报告:text2sql 重构票 #65 SSE 问答竖切(2026-10-17)

## 批准依据

> 用户 /implement 连续驱动票序;#65 的 UI 过目确认以用户后续 /implement 指令作实(已在对话声明此解释,可回退)。

## 已完成(TDD)

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `POST /chat` SSE(text/result/final/error;agent 工作线程+事件队列)、`POST /chat/stop`(注入终止事件)、`POST /session/{id}/reset`(存 connect 参数重建 agent);会话升级 _SessionEntry,/query 兼容 | agents/data/text2sql/api.py | 本批次 commit |
| 高 | 协议测试 5 条(流事件序列/404/stop 终止/reset 重建/事件字段)先红(3 failed)后绿 | tests/test_t2s_chat_api.py | 本批次 commit |
| 高 | 聊天面板:气泡、原生结果表(SQL+50 行截断+行数)、发送/停止切换、新会话清屏 | frontend/text2sql/src/ChatPanel.tsx, api.ts, App.tsx, i18n.ts | 本批次 commit |
| 中 | 浏览器冒烟 +1(fake agent 全链路:问→流→表 42→final→新会话清空);既有连接冒烟断言随 UI 演进更新 | tests/test_t2s_page.py | 本批次 commit |

## 验证结果

```
RED:  tests/test_t2s_chat_api.py -> 3 failed(端点不存在)
GREEN: chat+connect API 9 passed; 页面冒烟 2 passed
全量: pytest -q -> 2923 passed, 1 skipped(+5); mypy Success; ruff All checks passed!
前端: npm build / lint 全过
踩坑复现: heredoc 吃反斜杠致 f-string 断行(pitfalls 已有记录,本次再次命中,改用 Edit 修复)
python scripts/check_workflow.py -> 输出附于本批最终 commit 后(见对话)
```

## 前后差异

- 前:问答只有阻塞式 /query;React 页连接后无事可做。
- 后:/text2sql-next 可完整流式问答(真 LLM),停止/新会话可用,execute_sql 结果原生表格化。
- 测试:2918 → 2923 passed。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 富分析卡(schema/review/…)事件未透传 | /chat 只映射 text/tool_call/execute_sql/final | 混合协议的 HTML 透传部分属后续票 | 对应功能暂缺 | #68-#71 逐步补 |
| 低 | TestClient 对 SSE 整体缓冲,stop 测试改用 /chat/stop 轮询观察活跃性 | test_t2s_chat_api.py 注释 | httpx TestClient 行为 | 测试写法约束 | 已以纯 HTTP 缝解决 |
| 低 | 并发同会话 chat 未加锁(后发请求会抢占 _on_event) | api.py chat_stream | 单用户场景 | 边缘竞态 | 票 #67 前加会话级锁 |

## 未执行的步骤

- uitest smoke 全套件:未执行 —— 本票不触及既有 91 条用例路径;全量 pytest + 双冒烟覆盖;CI 兜底。
