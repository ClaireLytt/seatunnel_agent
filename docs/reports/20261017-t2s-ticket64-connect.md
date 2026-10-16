# 批次结果报告:text2sql 重构票 #64 连接竖切(2026-10-17)

## 批准依据

> 用户 /implement 启动 frontier 票;UI 过目后在 grilling Q0 回复 "yes" 确认收尾。

## 已完成(TDD)

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `POST /api/text2sql/connect`(服务端持会话,凭据一次性)+ `GET /session/{id}`;复用 _build_agent 的 schema/指标/agent 构建 | agents/data/text2sql/api.py | 本批次 commit |
| 高 | API 测试 4 条(connect 成功含表清单 / 未知方言 400 / 空库 400 / 未知会话 404)—— 先红(3 failed)后绿 | tests/test_t2s_connect_api.py | 本批次 commit |
| 高 | `frontend/text2sql` 新 workspace app:连接面板(九方言、sqlite 条件字段、a11y label 关联)、状态、会话卡;挂 /text2sql-next 开发路由 | frontend/text2sql/*, hub/ui.py | 本批次 commit |
| 中 | 浏览器冒烟:进程内 uvicorn 真连 SQLite,断言 Connected · 2 tables(先红:get_by_label 失败暴露 a11y 缺失,修复后绿) | tests/test_t2s_page.py | 本批次 commit |

## 验证结果

```
RED 证据: tests/test_t2s_connect_api.py -> 3 failed(端点不存在)
          tests/test_t2s_page.py       -> Timeout get_by_label("Database")(label 未关联)
GREEN:    test_t2s_connect_api.py 4 passed; test_t2s_page.py 1 passed
全量:     pytest -q -> 2918 passed, 1 skipped(+4); mypy Success (103 files); ruff All checks passed!
前端:     npm build / lint / prettier 全过(workspace 新成员 @seatunnel/text2sql-frontend)
人工过目: /text2sql-next 已起,用户确认
python scripts/check_workflow.py -> 输出附于本批最终 commit 后(见对话)
```

## 前后差异

- 前:连接只存在于 Gradio 浏览器会话,API 每请求都要带 db_config(密码反复传输)。
- 后:connect 一次返回 session_id,服务端 LRU 持 agent;React 页在 /text2sql-next 可真连数据库。
- 测试:2914 → 2918 passed。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | /query 尚未接受 session_id 复用 connect 会话 | api.py /query 仍要求每请求 schema | 属 #65(SSE 问答)范围 | connect 会话暂只被 /session 查询 | #65 实现 |
| 低 | 会话 LRU 上限 20 沿用旧值,无 TTL | api.py _SessionStore | 旧设计 | 多用户挤出早期会话 | 观察,必要时加 TTL |
| 低 | hub 起新实例时 SEATUNNEL_UI_KILL_PORT 杀旧实例,旧后台任务报 failed —— 已复现 2 次,属预期行为易误判为故障 | 任务 bplz2zu8u/bfufje5sj 等 | 端口抢占设计 | 误判 | 已记 docs/pitfalls.md |

## 未执行的步骤

- uitest smoke 全套件:未执行 —— /text2sql-next 是新增开发路由,91 条既有用例不经过它;全量 pytest + 新冒烟已覆盖;CI 在 PR 上会跑 smoke。
