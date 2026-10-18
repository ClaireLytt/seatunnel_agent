# 04: Playwright 页面测试 + i18n parity

**What to build:** tests/test_config_migrate_page.py(Playwright in-process uvicorn,照既有 test_<name>_page.py 先例):页面加载、单条迁移出 yaml 与报告、批量表单提交、语言切换;i18n parity 测试照 tests/test_datacompare_i18n.py 先例。等价覆盖退役的 YAML 用例。

**Blocked by:** 01, 02, 03

**Status:** ready-for-agent

- [ ] 页面测试覆盖单条/批量/语言切换,本地通过
- [ ] i18n parity 测试通过
- [ ] ruff/mypy + 定向测试通过
