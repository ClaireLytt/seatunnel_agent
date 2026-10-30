# 批次结果报告:contract-init-demo(2026-10-29)

## 批准依据

> 功能盘点轮用户批示:"go on"(推荐方案:1 `contract --init` 反向生成契约 + 2 governance_demo 演示目录;3 治理总览记入待办)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | contract --init:从 DDL 反向生成契约 YAML 底稿(列/类型落声明、已注释列标 comment: true、分区键落 partitioned_by),配 -o 落盘;生成即回灌校验为零违约 | contract_check/bootstrap.py, cli_cmds/checks.py | 本批次 |
| 高 | examples/governance_demo:一个目录植入全套病灶,六个治理 agent 全部命中(README 列明病灶与命令) | examples/governance_demo/{warehouse,grants,migration}.sql, contract.yaml, README.md | 本批次 |
| 中 | 防腐测试:逐 agent 断言演示目录的病灶种类集合 + init 往返零违约;四个扫描页默认目录切到演示仓并重建 | tests/test_governance_demo.py, 四个 App.tsx 与页测 | 本批次 |
| 低 | 指南补 --init 与演示目录;NEXT.md 增「治理总览页」待办 | docs/governance_guide.md, docs/NEXT.md | 本批次 |

## 验证结果

```
python -m pytest tests/test_contract_check.py -q      -> 23 passed in 3.76s
python -m pytest tests/test_governance_demo.py -q     -> 2 passed in 1.56s
python -m pytest -m uitest tests/test_{metaquality,contract,grants,ddlguard}_page.py -q
  -> 10 passed in 34.43s(默认目录切换后)
npm run build(四个页面)-> 全部 built
python -m pytest -q  -> 3622 passed, 1 skipped, 266 deselected in 164.60s
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
```

## 前后差异

- contract 采用成本:手写 YAML → `contract --init -d sql/ -o contract.yaml` 一条命令出底稿,删减后进仓即成门禁。
- 演示面:六个治理 agent 共用一个有血有肉的样例仓(此前默认 pii_demo 只有 PII 病灶),页面「扫描目录」默认即有完整输出。
- 踩坑:flow mapping 里 DECIMAL(16,2) 的逗号会截断 YAML 值 → 类型紧凑化后加引号输出;同时 _norm_type 改为空白不敏感(DECIMAL(16, 2) == decimal(16,2))。
- 全量测试 3616 → 3622(+6)。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- 治理总览页 /governance 已记入 NEXT.md 待办(前置:三个新 agent 的 RunLogger + stats REST)。
