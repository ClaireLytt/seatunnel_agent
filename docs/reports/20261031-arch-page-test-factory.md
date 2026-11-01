# 架构深化 — standard_page_tests 页面测试工厂

日期: 2026-10-31 分支: fresh

## 背景

/improve-codebase-architecture 复盘（报告: %TEMP%/architecture-review-20261031-203000.html）。
热点=本分支的 agent 工厂模式;四个候选中 Top recommendation 为页面测试工厂（Strong）:
42 份 test_*_page.py 是逐字复制的 Playwright 样板（~76 行/份）,真正独有的只有 7 个事实,
interface 几乎等于 implementation —— shallow module × 42,浏览器交互修复零 locality。

## 改动

- `tests/conftest.py` 新增 deep module `standard_page_tests(manifest, router_ref,
  mount, env_var, demo_dir, heading, run_button, expect_texts, llm_label)`:
  内部生成 page_url/nokey_url fixtures 与两条标准测试（run_flow 断言标题/按钮/
  期望文本/零 console error;nokey 走 LLM 复选框断言 inline 503）,测试名按
  manifest.name 命名,调用方 `globals().update(...)` 绑定。
- 迁移本分支 12 份页面测试为 ~30 行 spec：rollbackplan/contractgen/sqldiff/
  modelreview/duppipeline/maskpreview/mockdata/joinaudit/ddlevolve/dqrulegen/
  seatunnelgen/slaboard。
- 特例保留手写：alert_storm（AS004 专用断言）、双页 handoff 测试、更早期的
  30 份存量页面测试（后续按需渐进迁移,不在本次 scope）。
- 其余候选（共享 AgentReportPage 组件、CLI 命令工厂、脚手架配置继承）按
  "两个 adapter 才算真 seam"原则暂缓,记录在报告中。

## 验证

```
12 个迁移文件全量 uitest:
======================== 24 passed in 77.74s (0:01:17) ========================
All checks passed!   (ruff)
```

## Gate

```
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```
