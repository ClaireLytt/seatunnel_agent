# 批次结果报告:diff-livegrants(2026-10-29)

## 批准依据

> 功能盘点轮用户批示:"go on"(盘点池剩余两候选:⑨ contract --diff、⑩ grants×ddlguard 交叉检查;最初由 Spec 审查子代理提出)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `contract --diff`:反向漂移——用 --init 的新底稿对照已入仓契约,列出「契约没覆盖的新表」「已承诺表上的新列」(正向违约仍归 check);-F json 可机读,带 --fail-on 时有漂移 exit 1 | contract_check/bootstrap.py(diff_contract), cli_cmds/checks.py | 本批次 |
| 高 | ddl_guard × grant_scan 交叉检查:被 DROP/RENAME 的表若在同脚本的净授权面(GRANT/REVOKE 抵销后)仍挂授权,报「授权未回收」medium,detail 列出 principal 清单;REVOKE 抵销过的不误报 | ddl_guard/guard.py, report.py 双语标签 | 本批次 |
| 中 | 测试:交叉检查 1 条(命中/改名命中/已撤销不报)+ --diff 3 场景(新表/新列/自举往返零漂移)+ CLI gate;演示仓种 dim_ghost 活授权,防腐测试扩展 live_grants | tests/test_ddl_guard.py, tests/test_contract_check.py, examples/governance_demo/grants.sql, tests/test_governance_demo.py | 本批次 |
| 低 | 指南补 --diff 用法与「授权未回收」说明 | docs/governance_guide.md | 本批次 |

## 验证结果

```
python -m pytest tests/test_ddl_guard.py tests/test_contract_check.py -q -> 38 passed
python -m pytest tests/test_governance_demo.py -q -> 2 passed
python -m pytest -q  -> 3633 passed, 1 skipped, 272 deselected in 187.58s
ruff check src tests -> All checks passed!
mypy                 -> Success: no issues found in 177 source files
```

```
check_workflow 输出(提交后运行):
[PASS] AI 署名: 无 AI 署名(范围 origin/pso..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘
[PASS] 报告含验证输出
[PASS] floor: 无作弊变绿改动(范围 origin/pso..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/pso..HEAD)
```

## 前后差异

- 契约闭环补全最后一块:check 盯「现状违背承诺」,--diff 盯「承诺落后现状」,--init 负责起步——三面围住静默漂移。
- 治理 agent 第二次互相引用(第一次是 grants 用 pii 命中表):ddl_guard 复用 grant_scan 的解析与净面,零新规则维护成本。
- 全量测试 3628 → 3633(+5)。盘点池清空。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

无。
