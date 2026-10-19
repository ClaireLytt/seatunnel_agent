# 02: Playwright 对等覆盖与 DAG1-5 退役

**What to build:** 新 React 页的每个控件都有确定性 Playwright 覆盖,DAG1-5 yaml 用例退役且 uitest 套件仍全绿;i18n parity 测试保证双语 key 不漂移。

**Blocked by:** 01(React 页存在后才能测)

**Status:** ready-for-agent

- [ ] tests/test_dagcheck_page.py:smoke(标题/默认值/按钮)、环+断链(对等 DAG1)、分批+关键路径(DAG2)、不可调度表(DAG3)、坏目录无 traceback(DAG4)、英文流(DAG5)、非默认方言 spark(用 conftest.assert_dialect_switch)、空输入提示
- [ ] i18n parity 测试(test_seatunnel_i18n.py 模式)
- [ ] 删 cases/dagcheck.yaml;test_ui_testing.py 用例 floor 43→38;test_registry.py `_DATA_API_NAMES` 等硬编码更新
- [ ] `pytest -m uitest -k dagcheck` 全过;uitest smoke(--no-llm)全绿;ruff/mypy 通过
