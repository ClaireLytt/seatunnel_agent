# 04: 页测 + i18n parity + 触点清理 + 批次收尾

**What to build:** 维护者拥有 DSK1-DSK21 等价的自动化回归（SQLite 连库
fixture 等价用例、双桥接预填用例、LLM 回退确定性用例）与 zh/en parity
校验；旧触点干净移除；批次完整收尾。

**Blocked by:** 03 (React 页 B + cutover)

**Status:** ready-for-agent

- [ ] 删 cases/dataskew.yaml、ai_cases.yaml DSKA1、scroll.yaml SCR9、
      _fixtures.yaml connect_skew_sqlite；清 catalog.py dataskew 条目、
      page.py READY/.dsk-report-card/标签映射、hub/css.py dsk 相关段
- [ ] tests/test_dataskew_page.py：分析系列（DSK2-DSK7 规则等价）、空输入、
      清空、上传、历史、SQLite 连接+探针+一致性提示、en 切换、双桥接预填
- [ ] tests/test_dataskew_i18n.py：键齐全 + 旧文案逐字钉死 + cookie lng
- [ ] _DATA_API_NAMES 等硬编码核对；test_data_comparison 跨页 handoff 测试保持通过
- [ ] 批次收尾：全量 pytest、uitest smoke、批次报告落盘、check_workflow、
      双轴 code-review + fix-up
