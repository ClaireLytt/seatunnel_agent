# 03: D4 — 工厂加钩子 + 余 5 页测迁移

**What to build:** conftest make_page_url 加 `extra_mounts: list[tuple[str, manifest]] | None`(第二 dist 挂载,sql_review 双页桥接用)与 `post_setup: Callable[[monkeypatch, tmp_path], None] | None`(模块级打桩/seed,datacompare/dataskew 用);t2s/transpile 的 yield 元组改为工厂 page_url + 本地小 fixture 派生(db_path/tmp 输出目录);5 文件本地 _free_port/uvicorn fixture 删除;手写 zh cookie 的页测(config_migrate/conflint 等)改调 zh_page。

**Blocked by:** None(与 01/02 文件不相交)

**Status:** ready-for-agent

- [ ] `def _free_port` 仅剩 conftest 一处
- [ ] 5 文件页测 `-m uitest` 全绿(t2s 无 key 的 4 例既有环境失败除外,如实对照)
- [ ] ruff/mypy 绿
