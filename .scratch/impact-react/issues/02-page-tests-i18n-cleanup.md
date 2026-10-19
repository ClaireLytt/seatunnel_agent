# 02: Change Impact 页测 + i18n parity + 触点清理 + 收尾

**What to build:** 维护者拥有 IMP1-IMP8 等价的 Playwright 回归与 zh/en
parity 校验；`.st-imp-*` 触点零残留；批次完整收尾。

**Blocked by:** 01 (workspace + cutover)

**Status:** ready-for-agent

- [ ] 删 cases/impact.yaml、scroll.yaml SCR3；清 catalog.py impact 条目、
      page.py READY /impact 与 .st-imp-main 回退、asserts.py
      _PAGE_SCROLL_SELECTOR、css.py .st-imp-* 段（.st-set-* 保留）
- [ ] tests/test_impact_page.py（参照 test_lineage_page.py，
      examples/impact_demo）：IMP1-IMP8 等价 + 页签切换
- [ ] tests/test_impact_i18n.py（键齐全 + 旧文案逐字钉死 + cookie lng）
- [ ] 硬编码核对（test_registry/_DATA_ROUTES 保持 /impact 卡片）
- [ ] 批次收尾：全量 pytest、uitest smoke、批次报告落盘、check_workflow、
      双轴 code-review + fix-up
