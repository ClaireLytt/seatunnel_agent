# 批次结果报告:架构深化 C2·前端脚手架基座(2026-10-21)

## 批准依据

> 同 C1:用户经架构评审后依次 `/to-spec`、`/to-tickets`、`/implement-spec`(spec:.scratch/arch-deepen-2/spec.md);分支要求沿用 plat 直提。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票05 expand:frontend/shared 基座 7 文件(vite.base.ts 的 makeViteConfig({base,apiPath,url})、tsconfig×3 base、eslint/tailwind/postcss base);试点 doc_qa+issue_triage | frontend/shared/、两试点 ×7 叶子 | 03ed4bf |
| 高 | 票06 migrate A:8 workspace(orchestrator/llm_eval/prompt_lab/llm_cost/code_fix/web_task/uitest/text2sql) | 56 文件 +72/−733 | 5feee94 |
| 高 | 票07 migrate B:8 workspace(config_lint/dag_check/change_impact/config_migrate/data_comparison/data_lineage/data_skew/metric_diff;change_impact 的 /api/lineage、data_skew 的 /api/skew 等历史 apiPath 原样保留) | 56 文件 +72/−736 | 26f5b79 |
| 高 | 票08 migrate C:7 workspace(pii_scan/schema_drift/seatunnel/sql_fmt/sql_review/sql_testgen/sql_transpile;首轮只切 vite.config 被验收发现缺口,补完其余 6 文件/workspace) | 56 文件(7+49)+77/−791 | 本报告同批提交 |

**收尾核对(grep 均为空)**:全部 25 个 vite.config 走 makeViteConfig;全部 tsconfig.app.json 带 extends;全部 eslint.config.js 走 shared 基座。路径型字段(tsBuildInfoFile/baseUrl/paths/include/references)按 tsc 解析规则留叶子,非重复。

## 验证结果

```
每批切换 workspace lint+build -> 全部 exit 0(text2sql lint 除外,见遗留:既有 src 错误,stash 复原验证为 pre-existing)
ruff check src tests   -> All checks passed!(exit 0)
mypy                   -> Success: no issues found in 114 source files
pytest -q              -> 3286 passed, 1 skipped, 237 deselected
页测抽验(seatunnel 全套 + sql_review smoke)-> 6 passed(dist 可服务)
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                       -> PASS 22 · FAIL 0 · ERROR 0(runs/20261021_092644/report.html)
python scripts/check_workflow.py -> 随本批次收尾执行,输出附对话
```

## 前后差异

- 行数:25 workspace × 7 配置文件 −2,448 行(184+733+736+644+补完差额),基座 ~160 行一处;新 workspace 脚手架从 ~141 行 → 7 个 1–4 行文件。
- 局部性:vite/tsc/eslint/tailwind 策略升级一处生效;构建行为零变化(全部 build 绿、dist 被页测服务、产物与迁移前等价)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | text2sql lint 失败为既有 src 错误(6 error:no-explicit-any ×5、rules-of-hooks ×1) | 票06 以 stash 复原验证 pre-existing;BoardsView/MetricsView/SubscriptionsView | 旧代码未过严格规则 | lint 门禁对该 workspace 失效 | 另票修 src |
| 低 | data_skew src 1 条 react-refresh warning(既有) | 票07 汇报 | 同上 | 无 | 顺手修或忽略 |
| 低 | change_impact/data_comparison/data_lineage/llm_eval/llm_cost chunk >500kB 警告(既有) | build 输出 | 未 code-split | 体积提示 | 后续统一 manualChunks(此前批次已记录) |
| 低 | 票08 首轮漏切 6 文件/workspace,验收 grep 发现后补完 | 本报告票08 行 | 子代理理解偏差 | 已补完,无残留 | 无(流程按设计兜住) |

## 未执行的步骤

- `seatunnel-agent ui --build` 全量一键构建:未执行(25 个 workspace 已逐个 build 验证,页测抽验 dist 可服务;如需我可再跑一次整体命令)。
