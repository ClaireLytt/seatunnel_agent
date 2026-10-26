# 批次结果报告:UI 露出·缓存徽标 + 结果卡空行修复(2026-10-27)

## 批准依据

> 用户对"提交本批 → 做 uitest 补课"回复:"go on"(两张截图验收通过)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 语义缓存接入 UI:`chat()` 首轮空历史(=单问语义)走缓存,此前 UI 永远走 chat() 导致缓存只在 CLI 生效;命中后问答补入历史,追问带上下文走 LLM | agent.py | 本批 |
| 高 | 缓存命中发 `tool_result`+`final_answer` 事件 → SSE 结果卡与最终文本正常渲染;聊天气泡加绿色「⚡ 缓存命中 · 零 LLM」徽标 | agent.py, ChatPanel.tsx | 本批 |
| 高(既有 bug) | **结果卡行体全空修复**:`result_snapshot` 读 `rows` 而 execute_sql 载荷叫 `preview_rows`——所有聊天结果卡的表格行一直为空(行数标签正确,行体空)。修复 + 回归测试 | chart.py | 本批 |
| 低 | i18n 清理:订阅表单 "metrics" 缺键残留 → `subMetric` 中英补齐 | SubscriptionsView.tsx, i18n.ts | 本批 |

新增测试 3 条:chat 首轮缓存(零 LLM 断言/历史补录/追问走 LLM)、snapshot preview_rows 回归、既有脆弱用例补 API_KEY 隔离(上批遗留一行修)。

## 验证结果

```
python -m pytest tests/test_text2sql_examples.py -q -> 18 passed
npm run lint/build --workspace text2sql -> 通过
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 174 source files
python -m pytest -q          -> 3470 passed, 1 skipped, 243 deselected in 163.72s
真浏览器截图                -> 修复前(行体空,"2 rows" 标签在)与修复后(上海 80/北京 100
                               + 绿色徽标)两张,全程零 LLM 链路;探针已清理
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3468 → 3470 passed(+2,另 1 条为既有用例加固)。
- 行为:UI 用户首问命中已验证示例时零 LLM 直出(带可见徽标);**所有**聊天结果卡从空表变为显示预览行。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | uitest 用例未覆盖:订阅新表单/健康页/缓存徽标/结果卡行内容(正是行内容无断言才让空行 bug 存活) | 本批发现史 | 三批累积 | 回归靠人工截图 | 下一批专项补课 |

## 未执行的步骤

- uitest 专项用例:未执行(即下一批)。
- 其余无。
