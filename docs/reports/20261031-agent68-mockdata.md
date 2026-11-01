# Agent 68 mock_data — 测试数据生成

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/mock_data/`：generator（复用 sample_profile.profile_rows 列剖面 + mask_preview 敏感判定）、i18n、report、advisor_llm（可选数据集说明,只发策略不发数据）、api（make_text_router）、tools（MCP）、manifest（group quality, /mockdata）。
- 逐列策略：唯一整数列→自增序列;低基数列→按观测分布抽取;整数/小数→观测区间内随机（小数保留观测精度）;日期→观测窗口内随机;文本→取样长度随机;空值率逐列保留。
- 敏感列（手机号/身份证/邮箱/姓名/银行卡/地址/IP 等）**现场合成绝不取样**——测试验证生成值与样例真值零交集且格式合规。
- 确定性：同样例同种子逐字节相同（seeded random）。
- CLI `mockdata`（-f/--text/-n/--seed/--csv-out 另存/--llm）;API 载荷含完整 CSV;页面提供 Download CSV。
- React 页面 `frontend/mock_data/`：样例输入 + 行数/种子 + LLM 复选框 + CSV 下载。
- 测试：`tests/test_mock_data.py` 12 项（确定性/敏感零泄漏/区间日期空值率保形/CSV 回环）;`tests/test_mockdata_page.py` 双页面流。
- 示例 `examples/mockdata_demo/sample.csv`。

## 验证

```
tests\test_mockdata_page.py ..                                           [100%]
============================== 2 passed in 8.34s ==============================

tests/test_mock_data.py + test_sample_profile.py + test_mask_preview.py
  + test_registry.py + test_hub_pages.py
======================= 81 passed, 2 warnings in 13.83s =======================
All checks passed!   (ruff)
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
