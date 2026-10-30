# 批次结果报告:grant-scan(2026-10-29)

## 批准依据

> 功能盘点轮用户批示:"go on"(候选 2:权限面扫描,含与 pii_scan 的联动亮点)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | grant_scan 核心:正则解析 GRANT/REVOKE(方言容错),同键 REVOKE 净面;分级:公开授权 high、敏感表授权 high(跑同脚本 pii_scan 联动)、ALL 宽权限 medium、库级宽范围 medium | agents/data/grant_scan/{scanner,report}.py | 本批次 |
| 高 | 四个面:CLI `grants`(CheckSpec)、REST `/api/grants/scan`(ScanSpec)、聊天/MCP 工具(manifest 声明)、React 页 /grants | grant_scan/{api,tools,manifest}.py, cli_cmds/checks.py, frontend/grant_scan/ | 本批次 |
| 中 | 9 条单测(净面/分级/PII 联动/CLI 门禁/REST/发现接线)+ 2 条 Playwright 页测;锁文件同批更新(吸取上一批教训) | tests/test_grant_scan.py, tests/test_grants_page.py, frontend/package-lock.json | 本批次 |
| 低 | 治理指南加「收口:权限面」一节 | docs/governance_guide.md | 本批次 |

## 验证结果

```
python -m pytest tests/test_grant_scan.py -q            -> 9 passed in 3.19s
python -m pytest -m uitest tests/test_grants_page.py -q -> 2 passed in 12.13s
npm run build --workspace grant_scan                    -> built in 2.94s
npm run lint --workspace grant_scan                     -> clean
python -m pytest -q  -> 3605 passed, 1 skipped, 264 deselected in 150.75s
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

- 治理面从「找(hygiene)/规(metaquality)/护(pii)/诺(contract)」补上「收口(grants)」:谁被授了什么、敏感表是否外授。
- 联动是本批亮点:sensitive_grant 直接复用 pii_scan 对同脚本的命中结果,零新规则维护成本。
- 全量测试 3596 → 3605(+9),uitest 262 → 264(+2)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 部分撤销(REVOKE 子集权限)保守处理:原授权保留在净面里 | scanner.py 净面逻辑 | 语义上安全侧(宁多报不漏报) | 极端场景多报一条 | 真实误报出现再细化 |

## 未执行的步骤

无。盘点轮三项(contract_check / metaquality 规则 / grant_scan)至此全部交付。
