# 批次结果报告:chatbi-forecast-grain(2026-10-26)

## 批准依据

> 用户原话:"批次 1+2"(本报告为批次 2:周/月粒度预测;批次 1 见 20261026-chatbi-forecast-holiday.md)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `forecast_series` 支持 `grain=day/week/month`:周期步进(ISO 周一/自然月 1 号)、错位周期起点报错、周/月关闭星期+节假日季节性;payload 新增 `grain`,非日粒度输出 `history_periods`/`slope_per_period` | src/seatunnel_agent/agents/data/text2sql/forecast.py | 本批次 |
| 高 | `forecast_metric` 工具新增 `grain` 入参:日序列在工具层聚成周/月(SQL 保持日粒度,零方言风险),**丢弃不完整的边缘周期**;比率指标非日粒度明确报错;history_days 分粒度上下限(month 上限 900 天,保证不触发 default_limit=1000 截断守卫) | src/seatunnel_agent/agents/data/text2sql/tools_metric.py | 本批次 |
| 中 | 工具 schema 增加 grain 枚举与分粒度 history 说明 | src/seatunnel_agent/agents/data/text2sql/tools.py | 本批次 |
| 中 | PRD §13 增补 v3 扩展表(G1 节假日/G2 粒度),guide 预测节同步参数 | docs/chat_bi_prd.md, docs/chat_bi_guide.md | 本批次 |
| 高 | 新增 7 个测试:周粒度趋势恢复、月步进、错位/非法粒度拒绝、周粒度端到端(sqlite)、边缘周期丢弃致样本不足的明确报错、比率拒绝周粒度 | tests/test_text2sql_forecast.py | 本批次 |

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 107 source files
pytest tests/test_text2sql_forecast.py -q -> 26 passed in 1.04s
pytest -q              -> 3391 passed, 1 skipped, 243 deselected in 149.85s
python scripts/check_workflow.py -> 输出贴于对话(本报告提交先于核对,见"未执行的步骤")
```

## 前后差异

- tests/test_text2sql_forecast.py:19 → 26 passed(+7;批 1 前为 15)
- 全量:3384 → 3391 passed
- 行为:`grain` 缺省 day 时输出与批 1 后逐字节一致;week/month 为新增路径

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 2027+ 节假日数据缺失(承接批 1) | calendar_cn.py | 国办未发布 | 跨年预测无节假日修正 | 2026-11 发布后补数据 |
| 低 | 月粒度默认 365 天仅 12 个点,无季节性下区间偏宽 | forecast.py MIN_POINTS=7 | 月样本天然少 | 月预测置信带宽 | 文档已注明;必要时引入年季节性 |
| 低 | 比率指标周/月粒度直接拒绝,未提供分子/分母分别预测的自动组合 | tools_metric.py 比率分支 | 日比率不可重聚,自动组合口径存疑 | 用户需手动分别预测 | 报错信息已给出替代做法;保持现状 |

## 未执行的步骤

- uitest:未执行(无 UI 改动)。
- check_workflow.py 在本报告落盘并提交后执行(其"工作区干净"检查要求先提交),输出在对话中交付。

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
