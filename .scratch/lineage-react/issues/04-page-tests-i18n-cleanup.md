# 04: 页测 + i18n parity + 触点清理 + 批次收尾

**What to build:** 维护者拥有 LIN1-LIN11 等价的 Playwright 回归（建图/
查询/搜索/体检/坏目录/SeaTunnel 源/路径/SLA/快照保存与对比；LIN12 真
LLM 留手动，问答 SSE 以无 key 确定性路径覆盖）与 zh/en parity 校验；
lineage 触点干净移除且 /impact 不受损；批次完整收尾。

**Blocked by:** 03 (React 页 B + cutover)

**Status:** ready-for-agent

- [ ] 删 cases/lineage.yaml、lineage_advanced.yaml；清 catalog.py lineage
      条目；page.py READY /lineage 与 lineage 标签映射；css.py 仅删
      lineage 专属段（共用 .st-imp-* 选择器改写保留）
- [ ] tests/test_lineage_page.py（参照 test_dataskew_page.py，
      examples/lineage_demo）
- [ ] tests/test_lineage_i18n.py（键齐全 + 旧文案逐字钉死 + cookie lng）
- [ ] _DATA_API_NAMES 等硬编码核对；IMP 用例（/impact）在 smoke 中保持通过
- [ ] 批次收尾：全量 pytest、uitest smoke、批次报告落盘、check_workflow、
      双轴 code-review + fix-up
