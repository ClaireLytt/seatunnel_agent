# 批次结果报告:NL 建指标·引擎与确认流(2026-10-27)

## 批准依据

> 用户对"做 1(NL 建指标)"的方案回复:"go on"。本批范围:引擎工具 + REST 草稿/确认 + 提示词 + 测试;UI 确认卡下一批单做单验。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `draft_metric_entry`:候选条目按"现有文件全部条目 + 新条目"整体解析+交叉校验(落盘后 validate 会看到的完全相同的视角),重名显式拒绝;`append_metric_entry` 原子替换追加;`metrics_file_path` 单源 | metrics.py | 本批 |
| 高 | 工具 `draft_metric`:LLM 只起草,**零持久化**,草稿存 `rt.pending_metric_draft`;工具描述与提示词第 15 条双重强制"未确认不得声称已保存" | tools_metric.py, tools.py, prompts.py, runtime.py | 本批 |
| 高 | REST `POST /session/{id}/metrics/draft`(校验不落盘)与 `/draft/confirm`(用户确认→写文件→会话指标目录与系统提示词热更新) | api_metrics.py | 本批 |
| — | 指南"对话定义指标"段(明示 LLM 无直写口径文件路径) | docs/chat_bi_guide.md | 本批 |

新增测试 1 条(端到端 7 断言):坏表草稿 400 且文件不动 / 好草稿通过但 persisted=False 且文件不含 / 确认后文件含新旧条目且 metric_count=2 / 重复确认 400 / 重名草稿 400。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 175 source files
python -m pytest tests/test_t2s_connect_api.py tests/test_text2sql_metrics.py -q -> 106 passed
python -m pytest -q          -> 3482 passed, 1 skipped, 246 deselected in 168.73s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3481 → 3482 passed(+1,7 断言)。
- 行为:语义层录入新增对话路径,写入门槛三重:整体校验 → 显式确认端点 → 原子替换;未确认的一切交互零副作用。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | UI 确认卡未做(确认目前走 REST/编排) | 本批范围说明 | UI 批需单独截图验收 | 对话用户看得到草稿 YAML(final 文本)但要确认需调 REST | 下一批:SSE 转发 draft 事件 + ChatPanel 确认卡 |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
