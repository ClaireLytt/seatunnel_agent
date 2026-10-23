# 批次结果报告:src 遗留修复(config_migrate 白名单 + 守卫契约合并)(2026-10-23)

## 批准依据

> 用户:"修复掉遗留的问题"(针对 20261023-src-slim-down.md 遗留清单 2 条)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | config_migrate /batch 补目录白名单:`jobs_dir` 走 `require_dir`,`out_dir`(写入目标)过 `check_path_allowed`,env `CONFIG_MIGRATE_API_ALLOWED_DIRS`;新增 403 测试,3 个既有测试补 env | src/…/config_migrate/api.py、tests/test_config_migrate_api.py | cfd3d7d |
| 低 | 双契约合并:log_inspect 后端改结构化 bad_dir,前端改 postStructured + ApiError.code 本地化(i18n 补 bad_dir en/zh);纯文本版 require_dir 删除,结构化版更名为唯一的 `require_dir`(9 处调用点同步) | src/common/api_guard.py、src/…/log_inspect/api.py、frontend/log_inspect/* | cfd3d7d |

## 验证结果

```
ruff check src tests                        -> All checks passed!
mypy                                        -> Success: no issues found in 106 source files
pytest tests/test_config_migrate_api.py tests/test_log_inspect.py -> 39 passed
npm run lint/build --workspace log_inspect/config_migrate         -> OK
pytest log_inspect/config_migrate 的 i18n+page 测试               -> 15 passed
pytest -q(全量)                           -> 3332 passed, 1 skipped(新增 1 例 403 测试,3331→3332)
python scripts/check_workflow.py            -> 本报告提交后复跑,见对话
```

## 前后差异

- config_migrate /batch:任意存在目录可被迁移分析/写出 → 白名单外 403(`test_batch_migrate_outside_whitelist_403` 新增,passed)。**行为变化**:部署若用仓库外目录,需设置 `CONFIG_MIGRATE_API_ALLOWED_DIRS`。
- 目录守卫:`require_dir`(中文纯文本)+ `require_dir_structured` 两契约 → 单一 `require_dir`(结构化 bad_dir);log_inspect 错误提示由 `Error: 不是有效目录: …`(固定中文)→ 按页面语言本地化的 `⚠️ Not a directory: … / ⚠️ 不是有效目录: …`。
- 全量 pytest:3331 → 3332 passed。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- uitest smoke:未执行(页面行为由 15 例 i18n/page 定向测试覆盖;如需全量冒烟可随下批执行)。
