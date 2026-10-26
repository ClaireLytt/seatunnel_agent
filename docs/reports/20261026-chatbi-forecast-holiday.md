# 批次结果报告:chatbi-forecast-holiday(2026-10-26)

## 批准依据

> 用户原话:"批次 1+2"(本报告为批次 1:节假日外生变量;批次 2 周/月粒度另行报告)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 新增静态中国法定节假日/调休补班日历(2024–2026,逐字转录国办发明电〔2023〕7号 / 〔2024〕12号 / 〔2025〕7号) | src/seatunnel_agent/agents/data/text2sql/calendar_cn.py | 本批次 |
| 高 | forecast_series 加法节假日/补班日偏移(各类 ≥2 个观测日才启用;未覆盖年份自动退化不猜测);预测行标注 is_holiday;method 追加 +cn_holiday;payload 新增 holiday_offset / makeup_workday_offset | src/seatunnel_agent/agents/data/text2sql/forecast.py | 本批次 |
| 低 | forecast_metric 工具描述补一句节假日能力 | src/seatunnel_agent/agents/data/text2sql/tools.py | 本批次 |
| 高 | 新增 4 个测试:日历官方数量对账、节假日偏移生效、无节假日窗口零影响、单节假日样本不启用 | tests/test_text2sql_forecast.py | 本批次 |

数据来源(联网核验):2026 安排 2025-11-04 发布(人民网/中国政府网公报);2027 截至 2026-10-26 未发布,故日历只收 2024–2026。

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 107 source files
pytest tests/test_text2sql_forecast.py -q -> 19 passed in 1.29s
pytest -q              -> 3384 passed, 1 skipped, 243 deselected in 175.51s
python scripts/check_workflow.py -> 见批次 2 报告(两批同分支连续提交,收尾统一核对)
```

## 前后差异

- tests/test_text2sql_forecast.py:15 passed → 19 passed(+4)
- 全量:3380 → 3384 passed
- 行为:历史窗口含 ≥2 个法定节假日时,预测对节假日/补班日产生加法修正并标注;3 月等无节假日窗口输出与改动前逐字节一致(test_forecast_no_holidays_in_window_is_unchanged)

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 2027 及以后年份无节假日数据,预测窗口跨入时静默退化为无节假日修正 | calendar_cn.py CALENDAR_YEARS | 国办 2027 通知尚未发布(惯例 11 月发布) | 跨年预测在 2027 节假日上无修正 | 2026-11 官方发布后追加一批数据(纯数据改动) |
| 低 | 节假日偏移是单一均值,不区分春节/国庆等强度差异 | forecast.py _class_offset | 28 天默认窗口内通常只含一个假期,分假期估计样本不足 | 跨多个假期的长窗口里修正偏粗 | 保持现状;如需精细化再按假期分组 |

## 未执行的步骤

- uitest:未执行(本批次无 UI 改动)。
- check_workflow.py:推迟到批次 2 收尾统一执行(同分支连续两批)。

## check_workflow 补记(2026-10-27)

该检查(报告含验证输出)在本报告写就之后由 main 并入;补跑并粘贴真实输出。

```
python scripts/check_workflow.py --range "origin/main...HEAD"
[PASS] AI 署名: 无 AI 署名(范围 origin/main...HEAD)
[FAIL] 工作区: 工作区不干净:
M docs/reports/20261026-chatbi-audit-fixes.md
 M docs/reports/20261026-chatbi-forecast-grain.md
 M docs/reports/20261026-chatbi-forecast-holiday.md
 M src/seatunnel_agent/agents/data/text2sql/exporter.py
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/main...HEAD)
```
(工作区 FAIL 为本次补记时文件尚未提交的即时快照;提交后该项 PASS)
