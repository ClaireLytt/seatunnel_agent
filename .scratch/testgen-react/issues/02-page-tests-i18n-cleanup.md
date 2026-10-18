# 02: Test Data Generator 页测 + i18n parity + 触点清理 + 收尾

**What to build:** 维护者拥有 TGN1-TGN6 等价的 Playwright 回归与 zh/en
parity 校验；旧 YAML 与散落触点干净移除；批次完整收尾。

**Blocked by:** 01 (workspace + cutover)

**Status:** ready-for-agent

- [ ] 删 cases/testgen.yaml；清 page.py `.st-tgn-main` 选择器
      （catalog.py/css.py 已核无触点）
- [ ] tests/test_testgen_page.py（参照 test_sqlfmt_page.py）：预填生成+验证、
      WHERE 字面量、DDL 类型、非法 SQL 无 Traceback、取消验证、en 切换、
      空 SQL 提示
- [ ] tests/test_testgen_i18n.py（参照 test_sqlfmt_i18n.py）：键齐全 +
      旧文案逐字钉死 + cookie lng
- [ ] 批次收尾：全量 pytest、uitest smoke、批次报告落盘、check_workflow、
      双轴 code-review + fix-up
