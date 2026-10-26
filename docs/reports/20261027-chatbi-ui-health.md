# 批次结果报告:UI 露出·指标健康页(2026-10-27)

## 批准依据

> 用户对"提交健康页 → 做 3+4"回复:"go on"(截图验收通过)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中高 | REST `GET /session/{id}/metrics/health`:复用会话连接与指标库调 metric_health,零 LLM;无指标定义 400,未知会话 404 | api_metrics.py | 本批 |
| 中高 | UI 新视图「🩺 指标健康」(#health):红黄绿点/最新数据(+滞后天数)/7 天查询-失败-告警/月目标/订阅数;告警中行内 ⚠ 起始日;未连接空态引导;i18n 中英 8 键 | HealthView.tsx(新), App.tsx, api.ts, i18n.ts | 本批 |

新增测试 1 条:REST 健康端到端(真 sqlite+内联 metrics,latest_day 断言,未知会话 404)。

## 验证结果

```
python -m pytest tests/test_t2s_connect_api.py::test_session_metrics_health -q -> 1 passed
npm run lint/build --workspace text2sql -> 通过(useEffect 依赖用 useCallback 正解,零压制注释)
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 174 source files
python -m pytest -q          -> 3468 passed, 1 skipped, 243 deselected in 160.12s
真浏览器截图                -> 空态 + 连接后 5 指标表格(对话中交付,gmv 月目标 56.9%,
                               7 天告警列显示上一批 qlog 告警事件的真实计数);探针已清理
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3467 → 3468 passed(+1)。
- UI:治理视角(新鲜度/告警/失败/目标)从 CLI 搬进浏览器,与告警历史(上一批)数据贯通。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 既有用例 test_connect_returns_session_with_tables 单跑依赖环境 API_KEY(全量跑被顺序掩盖) | 本批排查记录 | 存量脆弱性,超本批范围 | 单测隔离性 | 给该用例补 monkeypatch.setenv(一行) |
| 中 | uitest 专项用例未覆盖订阅新表单与健康页(两批累积) | cases/chatbi.yaml | 真浏览器截图验收代偿 | 无自动回归 | 下一批与路线图 3+4 一起补 |

## 未执行的步骤

- uitest 专项用例:未执行(见遗留)。
- 其余无。
