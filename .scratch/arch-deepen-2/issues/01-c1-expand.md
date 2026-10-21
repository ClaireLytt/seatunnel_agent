# 01: C1 expand — conftest 工厂 + 2 个试点页测切换

**What to build:** conftest 新增 `make_page_url(manifest, router, mount, *, env: dict | None = None, neutralize_llm: bool = False, chdir_tmp: bool = False)`(返回 function-scoped fixture:端口分配、uvicorn 线程、dist-missing skip、启动等待、teardown)与共享 `zh_page` helper。试点切换 test_docqa_page.py(chdir 场景)与 test_triage_page.py(neutralize_llm 三重 monkeypatch 场景),删除其本地 _free_port/page_url/_zh_page。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 两试点文件 `-m uitest` 全绿;其余 23 个页测文件未动仍绿(抽 2 个跑)
- [ ] 工厂覆盖 env 注入/neutralize_llm/chdir_tmp 三种形态
- [ ] ruff/mypy 通过
