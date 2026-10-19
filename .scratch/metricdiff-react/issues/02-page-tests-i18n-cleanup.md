# 02: Metric Diff 页测 + i18n parity + 触点清理 + 收尾

**What to build:** 维护者拥有 MDF1-MDF5 等价的 Playwright 回归与 zh/en
parity 校验；触点干净移除；批次完整收尾。

**Blocked by:** 01 (workspace + cutover)

**Status:** ready-for-agent

- [ ] 删 cases/metricdiff.yaml；清 page.py `.st-mdf-main` 回退
      （catalog/css 经查无触点）
- [ ] tests/test_metricdiff_page.py（参照 test_schemadrift_page.py）：
      公式冲突、来源冲突+归一不误报、冲突引用文件名、坏目录、英文流程、
      空目录
- [ ] tests/test_metricdiff_i18n.py（键齐全 + 旧文案逐字钉死 + cookie lng
      + 方言/demo 预填钉定）
- [ ] 批次收尾：全量 pytest、uitest smoke、批次报告落盘、check_workflow、
      双轴 code-review + fix-up
