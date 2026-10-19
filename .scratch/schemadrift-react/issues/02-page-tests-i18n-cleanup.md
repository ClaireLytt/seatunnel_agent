# 02: Schema Drift 页测 + i18n parity + 触点清理 + 收尾

**What to build:** 维护者拥有 SDF1-SDF6 等价的 Playwright 回归与 zh/en
parity 校验；触点干净移除；批次完整收尾。

**Blocked by:** 01 (workspace + cutover)

**Status:** ready-for-agent

- [ ] 删 cases/schemadrift.yaml；清 page.py `.st-sdf-main` 回退
      （catalog/css/scroll 经查无触点）
- [ ] tests/test_schemadrift_page.py（参照 test_sqlfmt_page.py）：目录 demo
      对比、粘贴 DDL 漂移、无漂移、疑似改名、坏路径、英文流程、空输入
- [ ] tests/test_schemadrift_i18n.py（键齐全 + 旧文案逐字钉死 + cookie lng
      + 方言列表钉定）
- [ ] 批次收尾：全量 pytest、uitest smoke、批次报告落盘、check_workflow、
      双轴 code-review + fix-up
