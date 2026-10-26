# 批次结果报告:chatbi REST/MCP 门面补齐(2026-10-27)

## 批准依据

> 用户对第五轮候选清单(建议"1+2 一批")回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中高 | REST 零 LLM 端点 ×3:`POST /metrics/forecast` / `/metrics/target` / `/metrics/correlate`(薄壳复用 agent 工具函数;要求 db_config;工具错误转 400) | api_metrics.py | 本批 |
| 中 | MCP 工具 ×3:`forecast_metric` / `metric_target_progress` / `correlate_metrics`(`--allow-execute` 门控,与 execute_readonly_sql 同级;凭据仍只读服务端环境) | mcp_server.py | 本批 |
| — | 指南 REST/MCP 清单更新 | docs/chat_bi_guide.md | 本批 |

实现方式:两个门面都是 `Text2SQLRuntime` 薄壳直调 `tools_metric` 的工具函数——单一实现三入口(对话/REST/MCP),无逻辑复制。

新增测试 3 条:REST 三端点端到端(真 sqlite 28 天序列:forecast yhat=240 精确、target actual 恒等、correlate n_pairs=28、错误转 400)/ REST 缺 db_config 拒绝 / MCP forecast 端到端 + execute 门控断言(未开 allow_execute 时三工具不存在)。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 107 source files
python -m pytest tests/test_text2sql_metrics.py -q -> 89 passed in 10.98s
python -m pytest -q          -> 3445 passed, 1 skipped, 243 deselected in 157.71s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3442 → 3445 passed(+3)。
- 行为:编排平台(Dify/n8n)与 IDE(MCP)现在能拿到预测/达成率/相关性,此前仅对话用户可用;既有端点不变。
- 非 UI 改动,uitest 未执行。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 新订阅卡片(digest/断更/恢复/模型基线)硬编码中文,订阅 lang=en 收中文卡 | subscriptions.py 各卡片 body | 第五轮候选 3,本批未含 | 英文用户体验缺口 | 下一批接 i18n.py 文案字典 |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
