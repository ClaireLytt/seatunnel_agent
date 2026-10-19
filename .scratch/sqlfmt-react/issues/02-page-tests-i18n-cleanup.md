# 02: SQL Formatter Playwright 页测 + i18n parity + 触点清理

**What to build:** 维护者拥有覆盖页面外部行为的自动化回归：Playwright 页测
（FMT1-FMT6 等价 + 空输入 + bad_dir）与 zh/en parity 校验；旧 YAML 用例
及散落触点干净移除。

**Blocked by:** 01 (workspace + cutover)

**Status:** ready-for-agent

- [ ] 删 cases/sqlfmt.yaml；清 page.py `.st-fmt-main` 选择器；核对
      aiplatform.yaml:130 的 sql_fmt 断言是否受影响
- [ ] tests/test_sqlfmt_page.py（参照 test_conflint_page.py）：
      格式化往返 / 无需改动 / 风格提示 / 解析失败无 Traceback /
      目录检查 / en 切换 / 空输入 / bad_dir
- [ ] tests/test_sqlfmt_i18n.py（参照 test_conflint_i18n.py）：
      键齐全 + 旧文案逐字钉死 + cookie 驱动 lng
- [ ] _DATA_API_NAMES 移除 sql_fmt；其余硬编码核对
- [ ] 批次收尾：全量 pytest、uitest smoke、批次报告落盘、check_workflow、
      双轴 code-review + fix-up
