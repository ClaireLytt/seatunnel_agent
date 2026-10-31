# 批次结果报告:性能套件四~八期两轴评审修复(2026-10-31)

## 批准依据

> /code-review(固定点 1080353^,Standards + Spec 双轴)+
> "有什么需要改的"

## 评审结论

- Standards 轴:0 项硬违规(commit 规范/不删文件/复用/报告落盘全部
  合规);6 条 Fowler 判断题级 smell。
- Spec 轴:五期 plan 的全部 P/W 行均落地且有闸门;2 处 demo 缺口;
  issue #10 的 uitest YAML 用例组未覆盖新能力(面大,留待单独批次)。

## 已修复

| 来源 | 内容 |
| --- | --- |
| Standards#1 | check_runner.require_with():9 处手写 "--X 需配合 --Y" UsageError 收敛为一个助手(perf_ops x8 + skew x1) |
| Standards#4 | _salted_ok 更名 _salted_estimate(返回三元组,不是布尔);perf_report 的 t["hint"][2:] 魔法切片改 removeprefix("> ") |
| Standards#6 | md_table / math 的函数内 import 全部提到模块顶部(无循环依赖) |
| Spec#1 | 补 examples/slowquery_demo/metrics_fast.json(--diff 的 A 侧);examples/dagconflict_demo/scenario.json 两个 DAG 补 deadline 字段;新增 demo 对的 --diff 回归用例 |

## 按记录跳过

- Standards#2 三处组合胶水:两轮审查均判"第 5 个入口面出现再抽"。
- Standards#5 裸 dict 返回:与 render_* 配对惯例一致,改 dataclass
  收益低于 churn。
- Standards#3 perf_report 私有 i18n 字典:仅一处、双语齐全,迁移到
  i18n.py 模式等该命令长出第二个消费者再做。
- Spec#2 uitest YAML 用例组:真实缺口,但涉及 uitest 框架接入,
  不混入本次小修,留待单独批次。

## 验证结果

```
pytest tests (非 uitest) -> 3849 passed, 1 skipped
ruff src/seatunnel_agent -> All checks passed
mypy(触及的 43 个文件) -> no issues
python scripts/check_workflow.py --range origin/main...HEAD ->
[PASS] AI 署名: 无 AI 署名(范围 origin/main...HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出
[PASS] floor: 无作弊变绿改动(范围 origin/main...HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/main...HEAD)
```
