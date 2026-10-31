# Agent 61 mask_preview — 脱敏预览

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/mask_preview/`：masker（复用 sample_profile.parse_rows 与 pii_scan.DEFAULT_RULES）、i18n、report、advisor_llm（可选策略说明,只发规则元数据不发数据值）、api（make_text_router）、tools（MCP）、manifest（group governance, /maskpreview）。
- 判定：列名对 pii_scan 规则库（强/弱正则）+ 值形态（国内手机号/身份证 15·18 位/邮箱/银行卡,非空值 ≥60% 命中）双通道,报告标注判定依据（列名/值形态/两者）。
- 保格式值级脱敏：138****0001、110101********1234、x***@example.com、**** **** **** 3445、王**、地址前 6 字+****、薪资全遮、IP 后两段遮、默认首尾保留。
- 边界：pii_scan 从 DDL+血缘出 SQL 级脱敏方案;本 agent 直接脱数据行,外发测试/演示前最后一道检查。
- CLI `maskpreview`（-f/--text/--preview-rows/--llm/--fail-on-high CI gate）。
- React 页面 `frontend/mask_preview/`：数据行输入 + 预览行数 + LLM 复选框,演示预填 4 行含手机号/身份证/邮箱/姓名。
- 测试：`tests/test_mask_preview.py` 10 项;`tests/test_maskpreview_page.py` 双页面流。
- 示例 `examples/maskpreview_demo/users.csv`。
- 全量套件后台跑：4410 passed, 1 skipped;唯一 error 为 conftest 泄漏守卫检测到套件运行期间并发写入的本批新文件（开发与套件并发所致,非真实失败,本批提交后消除）。

## 验证

```
tests\test_maskpreview_page.py ..                                        [100%]
============================== 2 passed in 8.37s ==============================

tests/test_mask_preview.py + test_pii_scan.py + test_registry.py + test_hub_pages.py
======================= 92 passed, 2 warnings in 16.94s =======================
All checks passed!   (ruff)

full suite (background): 4410 passed, 1 skipped, 362 deselected
```

前端 `npm run lint` 零告警，`npm run build` 成功。

## Gate

```
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```
