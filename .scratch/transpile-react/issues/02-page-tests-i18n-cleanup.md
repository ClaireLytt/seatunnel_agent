# 02: SQL Transpile Playwright 页测 + i18n parity + 触点清理

**What to build:** 维护者拥有覆盖页面外部行为的自动化回归：Playwright 页测
（TRP1-TRP9 等价；TRP6 走 no-key 确定性路径；桥接预填用例）与 zh/en parity
校验；旧 YAML 用例及散落触点干净移除。

**Blocked by:** 01 (workspace + cutover)

**Status:** ready-for-agent

- [ ] 删 cases/transpile.yaml；清 catalog.py AGENT_ROUTES/LABELS transpile 条目；
      清 page.py READY `"/transpile"` 与 `.st-trp-side`/`.st-trp-main` 选择器
- [ ] tests/test_transpile_page.py（参照 test_sqlfmt_page.py）：单条翻译/
      重定目标/坏 SQL 无 Traceback/批量目录/批量写出/坏目录/空输入/
      en 切换/advice no-key/桥接预填
- [ ] tests/test_transpile_i18n.py（参照 test_sqlfmt_i18n.py）：键齐全 +
      旧文案逐字钉死 + cookie 驱动 lng
- [ ] 批次收尾：全量 pytest、uitest smoke、批次报告落盘、check_workflow、
      双轴 code-review + fix-up
