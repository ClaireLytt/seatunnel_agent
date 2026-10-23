# 批次结果报告:src-slim-down(bad_dir 守卫单源化 S01–S02)(2026-10-23)

## 批准依据

> 用户通过 `/implement-spec` 指令批准实现 `.scratch/src-slim-down/spec.md` 全部票据(01/02)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `require_dir_structured` 入 common/api_guard(白名单→存在性→结构化 bad_dir),改写 6 个路由(config_lint、dag_check、data_lineage、pii_scan、sql_fmt、sql_transpile) | src/seatunnel_agent/common/api_guard.py 等 | 9cf6954 |
| 高 | common/api_factory 的 /check 工厂同样改用共享守卫(调查阶段漏计的第 8 处副本) | src/seatunnel_agent/common/api_factory.py | 6eea372 |
| 低 | 删除 data_lineage agent 无调用者的 reset() | src/…/data_lineage/agent.py | c3f96c6 |

净效果:src/ 9 文件,+37/−69 行。顺带消除 config_lint 中冗余的双重校验(结构化守卫后又调 require_dir,后者错误不可达)。

**命名说明**:api_guard 已存在 `require_dir`(中文纯文本 detail,log_inspect 在用),故新守卫命名 `require_dir_structured`,两契约并存。

**范围调整**:config_migrate 的 bad_dir 变体保留 inline——它缺白名单检查,套用共享守卫会新增 403(行为变化),见遗留清单。

## 验证结果

```
ruff check src tests                 -> All checks passed!
mypy                                 -> Success: no issues found in 106 source files
pytest(6 个代理 API 测试)          -> 338 passed, 1 skipped in 20.41s
pytest tests/test_api_factory.py     -> 5 passed
pytest tests/test_data_lineage.py    -> 137 passed, 1 skipped
pytest -q(全量)                    -> 3331 passed, 1 skipped, 242 deselected
python scripts/check_workflow.py     -> 本报告提交后复跑,见对话
```

UI 未改动,未跑 uitest(纯后端行为保持重构,页面契约由既有 API 测试与前批页面测试锚定)。

## 前后差异

- bad_dir 守卫:8 份副本(7 路由 + api_factory)→ 共享 `require_dir_structured` 1 份 + config_migrate 1 份记录在案的变体(grep `"code": "bad_dir"` 仅余 api_guard 本体 + config_migrate)。
- 全量 pytest:前后均 3331 passed(行为不变)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 高 | config_migrate /batch 缺目录白名单检查(仅 is_dir→bad_dir),与其余目录型端点的安全基线不一致 | src/…/config_migrate/api.py:60-67;grep check_path_allowed 无命中 | 历史遗漏 | 网络入口可对任意存在目录发起迁移分析 | 单独小批次补 `require_dir_structured(jobs_dir, "CONFIG_MIGRATE_API_ALLOWED_DIRS")` + 前端/测试同步(需你批准,因新增 403 属行为变化) |
| 低 | `require_dir`(纯文本)与 `require_dir_structured` 双契约并存 | api_guard.py | log_inspect 仍用旧契约 | 两个相似函数 | 待 log_inspect 前端支持 bad_dir 本地化后合并 |

## 未执行的步骤

- uitest smoke:未执行(无 UI 改动)。
- config_migrate 白名单补齐:未执行(行为变化,超出本批"行为保持"范围,等待圈选)。
- /implement-spec 模板的 worktree/并行/集成分支/PR 流程:未执行(CLAUDE.md 禁止,串行于 dev)。
