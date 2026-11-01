# Agent 90 topic_schema — 消息 Schema 对比

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/topic_schema/`：differ（纯 JSON 解析,无新依赖,Avro record 与 JSON Schema 自动识别）、i18n、report、advisor_llm（可选发布通报）、api（make_text_router）、tools（MCP）、manifest（group build, /topicschema）。
- 兼容规则（对齐 schema registry 语义）：BACKWARD=新 Schema 读旧数据,新增无默认值字段即破坏;FORWARD=旧读者扛新数据,删除无默认值字段即破坏;full 双向同查。类型只认 Avro 升格链（int→long→float→double、string↔bytes）或 union 仅加 null 的拓宽;JSON Schema 另查"可选→必填"翻转。
- 分级：破坏所选模式=breaking,只破坏另一模式=risk,其余=info;结论 COMPATIBLE/INCOMPATIBLE。
- 边界：schema_drift 读 SQL DDL,本 agent 读消息世界的 Schema——全新输入域。
- CLI `topicschema`（--old/--new/--mode/--llm/--fail-on-breaking CI gate）。
- React 页面 `frontend/topic_schema/`：双 Schema 输入 + 模式 + LLM 复选框。
- 测试：`tests/test_topic_schema.py` 10 项（三模式分级/升格链与 null 拓宽/JSON Schema 必填翻转/flavor 混用拒绝/gate 双向）;页面测试 standard_page_tests 工厂 spec。
- 示例 `examples/topicschema_demo/{old,new}.json`。

## 验证

```
tests\test_topicschema_page.py ..                                        [100%]
============================== 2 passed in 7.85s ==============================

tests/test_topic_schema.py + test_registry.py + test_hub_pages.py + test_collision_guards.py
======================= 47 passed, 2 warnings in 14.77s =======================
All checks passed!   (ruff)
```

前端 `npm run lint` 零告警，`npm run build` 成功。

## Gate

```
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```
