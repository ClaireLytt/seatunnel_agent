# 批次结果报告:Agent 32 资源消耗预测(2026-10-31)

## 批准依据

> 30-35 批次计划第 3 步

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | sql_cost:SQL × 表统计 → 代价卡。扫描量=字节×分区裁剪折扣×物理读取列集比;join shuffle(小表低于 10MB 走广播)、聚合 exchange;输出行(FK 假设+聚合收缩 x10);内存峰值/核·秒/建议并行度/0.5x-2x 耗时区间;假设随报告列出;清单缺表点名排除不猜 | agents/data/sql_cost/ | (本批) |
| 高 | 三入口:/sqlcost 页(SQL+统计双输入)+ MCP 工具 + REST;示例、6 个单测、1 个页面回归 | frontend/sql_cost, tests | (本批) |

## 验证结果

```
pytest tests/test_sql_cost.py -> 6 passed
  (折扣公式逐项:100GiB/365×(3/20);shuffle=两侧+聚合一遍;广播分支 shuffle=0;
   缺表 missing 不计总量;0.5x-2x 区间恒等式)
pytest -m uitest tests/test_sqlcost_page.py -> 1 passed
pytest tests -q -> 3796 passed, 1 skipped
ruff / mypy(sql_cost 7 files) -> 全绿
npm run lint/build --workspace sql_cost -> 通过
python scripts/check_workflow.py --range origin/main...HEAD -> [PASS] x6
```

## 前后差异

- 跑前有数:扫描/shuffle/内存/耗时量级卡,与 sql_perf(计划事实)、
  index_advisor(建模建议)构成"跑前三件套"。
