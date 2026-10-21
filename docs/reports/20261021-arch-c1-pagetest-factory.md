# 批次结果报告:架构深化 C1·页测夹具工厂(2026-10-21)

## 批准依据

> 用户经 /improve-codebase-architecture 评审报告后依次调用 `/to-spec`、`/to-tickets`、`/implement-spec` 启动实施(spec:.scratch/arch-deepen-2/spec.md,首选推荐 C1);分支要求沿用:"就在现在的分支开发不允许切换新分支"(plat)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票01 expand:conftest 落 make_page_url(env/"{tmp}" 占位/None 删变量/neutralize_llm/chdir)与 zh_page;试点 docqa+triage | tests/conftest.py、tests/test_{docqa,triage}_page.py | b67c56f |
| 高 | 票02 migrate A:8 文件(orchestrator/llmeval/promptlab/llmcost/codefix/webtask/dagcheck/metricdiff) | tests/test_*_page.py ×8 | d527538(+59/−471) |
| 高 | 票03 migrate B:6 文件(config_migrate/conflint/impact/lineage/pii/schemadrift) | tests/test_*_page.py ×6 | 0ed4083(+29/−258) |
| 高 | 票04 migrate C:4 文件(sqlfmt/testgen/seatunnel/uitest,后两个以 autouse 伴随 fixture 承接打桩) | tests/test_*_page.py ×4 | 本报告同批提交,+28/−162 |

**正当保留(5 个,工厂刻意不覆盖的真差异)**:datacompare(模块级 store setattr 隔离)、dataskew(seed+模块全局)、t2s(fixture yield 元组+双服务器)、transpile(yield 元组)、sql_review(双 dist mount)。grep 证据:`def _free_port` 仅剩 conftest + 这 5 个文件。

## 验证结果

```
ruff check src tests   -> All checks passed!(exit 0)
mypy                   -> Success: no issues found in 114 source files
pytest -q              -> 3286 passed, 1 skipped, 237 deselected
pytest -m uitest(各批定向)-> 票01: 12 passed · 票02: 45 passed · 票03: 95 passed · 票04: 26 passed
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                       -> PASS 22 · FAIL 0 · ERROR 0(runs/20261021_085329/report.html)
python scripts/check_workflow.py -> 随本批次收尾执行,输出附对话
```

## 前后差异

- 行数:20 个页测文件夹具样板 −1,011 行(471+258+162+试点 ~120),共享实现 ~110 行一处(conftest)。
- 局部性:uvicorn 启动/端口/dist-skip/无 key 中和逻辑从 20 处收敛到 1 处;后续页面迁移的页测夹具 = 1 行声明。
- 行为零变化:全部页测与全量 pytest 通过,数字与迁移前一致(3286 passed)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | test_sql_review_page.py::test_sql_review_page_stats_refresh 既有失败(环境相关,本批未改该文件) | 单跑复现;fixture 只打桩 ReviewLogger.log,/stats 读到本机真实 review 历史(2026-10-18~20),"No review records yet." 不出现 | 测试依赖本机日志为空 | 本机全量 uitest 跑该文件会红 | 另票:fixture 补打桩 stats 数据源(REVIEW_LOG_PATH 之类 env) |
| 低 | 5 个保留文件仍带本地夹具 | grep 清单见上 | 形态为真差异(元组 yield/双 mount/模块级打桩) | 无——不属重复 | 保持;若未来工厂需要可加 extra_mounts/post_setup 钩子 |
| 低 | seatunnel/uitest 截图测试会重生成 docs/reports/shots/*.png(像素微差) | 本批两次出现,已 git checkout 还原 | 截图测试副产物 | 工作区噪音 | 可考虑截图测试输出改到 runs/ 另票 |

## 未执行的步骤

- C2(脚手架工厂,票 05–08):未执行,按票链接续进行。
