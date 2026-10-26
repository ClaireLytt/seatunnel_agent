# 批次结果报告:指标草稿 UI 确认卡(2026-10-27,全线终批)

## 批准依据

> 用户对"做 1(UI 确认卡)"回复:"go on";验收说明后再次回复:"go on"(验收通过)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中高 | SSE 转发 `draft_metric` tool_result 为 `metric_draft` 事件(仅 success) | api.py | 本批 |
| 中高 | ChatPanel 草稿卡:标题明示"已校验,未保存"+ YAML + 确认按钮 → confirm 端点 → 绿色"已写入,目录已热更新";失败走错误气泡;i18n 中英 3 键 | ChatPanel.tsx, api.ts, i18n.ts | 本批 |
| — | fake agent 补 draft 分支(真 SchemaStore 走通确认链);PR 草稿补第三波(行级权限/NL 建指标/告警聚合)并更新数字 3482/22 | tests/test_t2s_page.py, docs/PR_DRAFT_uiskill.md | 本批 |

新增 Playwright 用例 1 条:发问→卡片含 "NOT saved"+YAML→断言 metrics 文件不存在(草稿零落盘)→点确认→"Saved"→断言文件真含新条目。

## 验证结果

```
npm run lint/build --workspace text2sql -> 通过
python -m pytest -m uitest tests/test_t2s_page.py -q -> 22 passed(21→22)
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 175 source files
python -m pytest -q          -> 3482 passed, 1 skipped, 247 deselected in 166.82s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- UI:"对话定义指标"闭环——LLM 与口径文件之间始终隔着一次人类点击,且该点击前的一切交互零落盘(浏览器断言)。
- 浏览器回归 21→22;全量测试持平 3482。

## 未解决问题 / 遗留清单

无。**全线终批**:引擎、三门面、UI、五层安全、运维工具、demo、周报、两个重件与完整回归体系均已交付;剩余仅 PR 创建与任务收尾(用户动作)。

## 未执行的步骤

无。
