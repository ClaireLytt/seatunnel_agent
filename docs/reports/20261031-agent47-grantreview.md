# 批次结果报告:Agent 47 权限申请审核 grant_review(2026-10-31)

## 批准依据

> 用户:"适配以上的agent 制定好方案后一步步执行"(36–47 清单)。
> docs/data_agents_36_47_plan.md 里程碑 12:47 grant_review(套件二收口,
> 36–47 全部完成)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性审核核心:申请单 JSON(单份/列表)× 内置敏感级词表(S3 直接标识与资金 25 分/个、S2 准标识 5 分/个),整表 +20、非写角色要写 +30、超期/永久 +8/15、用途过短 +15;70 分拒绝、40 分降级并给具体降级建议(脱敏/按列/只读/压期限/补用途) | src/seatunnel_agent/agents/data/grant_review/reviewer.py | 本批 |
| 高 | zh/en 报告 + i18n + LLM 逐份回复草稿(opt-in) | grant_review/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest(governance 组) | grant_review/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent grantreview`(--llm/--fail-on-reject) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,demo 预填三份申请) | frontend/grant_review/* + workspace 注册 | 本批 |
| 中 | 示例申请单 + 单测 17 条 + 页面回归 2 条 | examples/grantreview_demo/applications.json · tests/test_grant_review.py · tests/test_grantreview_page.py | 本批 |
| 中 | 修复命令名冲突:43 的 CLI 与 data_lineage 既有 `datadict` 撞名,改为 `dictgen`(test_lineage_dictionary 两例因此恢复通过) | src/seatunnel_agent/cli_cmds/quality_ops.py · tests/test_data_dict.py | 本批 |
| 低 | 计划文档 12 个里程碑全部勾选 | docs/data_agents_36_47_plan.md | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_grant_review.py -q      -> 17 passed
python -m pytest -m uitest tests/test_grantreview_page.py -q -> 2 passed
python -m pytest tests/test_data_dict.py tests/test_lineage_dictionary.py tests/test_grant_review.py -q -> 39 passed
python -m pytest tests -q                           -> 4072 passed, 1 skipped, 322 deselected
seatunnel-agent grantreview -f applications.json -> 拒绝 li4(80)/降级 wang5(58,S3 脱敏+压期限)/批准 zhang3(5)
npm run build (frontend/grant_review)               -> built in 2.94s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:governance 组新增 /grantreview 卡片,REST/MCP/CLI/React
  四入口齐备;与 grant_scan 分工明确(审已授出的面 vs 审申请单风险)。
- 36–47 共 12 个 agent 全部落地(质量异常套件 36/37/38/39/40/41 +
  资产治理套件 42/43/44/45/46/47),每个独立提交、gate 全 PASS。
- 测试:本批新增 17+2 条;全量 4072 passed(改动前 4053),0 失败。

## 遗留

- 无。36–47 计划收口;后续可沿 phase 模式对单个 agent 叠加增强。
