# 02: PII Scan 页测 + i18n parity + 触点清理 + 收尾

**What to build:** 维护者拥有 PII1-PII6 等价的 Playwright 回归与 zh/en
parity 校验；触点干净移除；批次完整收尾。

**Blocked by:** 01 (workspace + cutover)

**Status:** ready-for-agent

- [ ] 删 cases/pii.yaml；清 page.py `.st-pii-main` 回退
      （catalog/css 经查无触点）；内置用例下限随 YAML 缩减同步
- [ ] tests/test_pii_page.py（参照 test_metricdiff_page.py）：demo 目录、
      粘贴 SQL、已脱敏不升级、坏目录、未命中、英文流程、空输入
- [ ] tests/test_pii_i18n.py（键齐全 + 旧文案逐字钉死 + cookie lng +
      方言/demo 预填钉定）
- [ ] 批次收尾：全量 pytest、uitest smoke、批次报告落盘、check_workflow、
      双轴 code-review + fix-up
