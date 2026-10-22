# 02: 退役 Gradio 旧页与测试迁移

**What to build:** 删 `agents/devops/secret_scan/ui.py`；清 `ui_testing/cases/devops.yaml` 的 SEC1/SEC2 用例；新增 `tests/test_secret_scan_page.py`（Playwright in-process uvicorn，等价覆盖 SEC1：密码赋值命中且页面无明文）；更新 `tests/test_hub_pages.py` `_DEVOPS_ROUTES` 与 `tests/test_registry.py` 硬编码到现状。Python i18n 只删 UI-chrome key，report.py 的渲染 key 保留。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] ui.py 删除，grep 无残留引用
- [ ] SEC1/SEC2 yaml 用例移除，等价 Playwright 页测通过
- [ ] test_hub_pages / test_registry 更新后通过
- [ ] 截图前后对比（旧页用 git worktree 起迁移前 commit）
- [ ] ruff / mypy / pytest / uitest smoke 通过，check_workflow.py 通过
