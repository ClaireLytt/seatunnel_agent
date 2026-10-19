# 02: Config Lint Playwright 页测 + i18n parity + 触点清理

**What to build:** 维护者拥有覆盖 Config Lint 页外部行为的自动化回归：
Playwright 页面测试（单配置 lint 往返、目录往返、坏目录提示、语言切换）
与 zh/en i18n parity 校验；旧 uitest YAML 用例及散落触点被干净移除，
后端 i18n 只保留报告渲染所需键。

**Blocked by:** 01 (workspace + cutover)

**Status:** ready-for-agent

- [ ] 删除 conflint 的 uitest YAML 用例及 catalog/page 中对应条目
- [ ] 新建 Playwright 页面测试（参照 config_migrate 页测先例）：四个场景全绿
- [ ] i18n parity 测试：i18next zh/en 键齐全；后端 i18n 裁剪为仅报告键
- [ ] registry/ui_testing 测试中的 conflint 硬编码名单更新，orchestrator 路由映射保持有效
- [ ] 批次收尾：全量 pytest、uitest smoke（--no-llm）、批次报告落盘、check_workflow PASS
