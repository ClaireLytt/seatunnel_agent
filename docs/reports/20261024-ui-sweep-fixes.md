# 批次结果报告:UI 巡检修复(ui-sweep-fixes)(2026-10-24)

## 批准依据

> 用户在 spec→tickets 流程后以 `/implement-spec` 启动实现,并在拆票确认时回复:"确认,发布票据";retro 项以"1-4"圈选落实。spec 与 6 张票见 `.scratch/fix-ui-sweep-findings/`。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票01 seatunnel Demo 诚实化:demo 配置写 configs/(dir-guard 内)、由 write_config 工具真实写入、总结按工具真实结果推导(新增 demo_failed i18n) | agents/data/seatunnel/{api,rendering}.py | 61fe90e |
| 高 | 票01 补:demo 测试 chdir tmp_path、demo 运行产物 gitignore、回滚误提交的 configs/demo_fake_to_console.conf | tests/test_seatunnel_api.py, .gitignore | 51e7e3c |
| 中 | 票02 i18n:testgen notes/warnings 走 i18n 表并透传 lang;lineage render_health 本地化 + /check 接 lang + 前端传语言;orchestrator 无 LLM 降级用英文描述表 | sql_testgen/{generator,i18n,api}.py, data_lineage/{render,api}.py, orchestrator/{router,catalog}.py, frontend/data_lineage | c73f772 |
| 中 | 票03 Text2SQL 查询日志 question 永不为空(sink 兜底 [channel] 标签);History 旧空行显示 — | text2sql/qlog.py, frontend/text2sql/HistoryView.tsx | a69a9d4 |
| 中 | 票04 MCP Toolbox 6 个 skew 工具补 zh/en 描述 + 注册表漂移守卫测试 | mcp_toolbox/ui.py, tests/test_mcp_toolbox.py | 0a941b2 |
| 中 | 票05 uitest 报告 iframe sandbox=allow-scripts(替换 allow-same-origin),Playwright 回归用例(脚本执行 + console 无 Blocked 错误) | frontend/uitest/App.tsx, tests/test_uitest_page.py | 4eee337 |
| 中 | 票06 secretscan password_assign 匹配 *_password/_pwd 前缀标识符,占位符过滤不变(正反用例) | secret_scan/rules.py, tests/test_secret_scan.py | c2d746b |
| 低 | demo_failed 登记进 backend i18n key 白名单守卫 | tests/test_seatunnel_i18n.py | 5e94576 |
| 低 | retro:测试污染仓库 session 守卫(_no_repo_pollution)、t2s history 测试自设 API_KEY、pitfalls 两条 | tests/conftest.py, tests/test_t2s_history_api.py, docs/pitfalls.md | 1cc4d7d |

## 验证结果

```
ruff check src tests scripts                      -> All checks passed!
mypy                                              -> Success: no issues found in 107 source files
pytest -q(全量)                                   -> 3360 passed, 1 skipped, 243 deselected, 2 warnings in 137.38s
pytest tests/test_uitest_page.py -m uitest -q     -> 2 passed in 14.17s(真浏览器 Playwright)
python -m seatunnel_agent...ui_testing run --suite smoke --no-llm
                                                  -> PASS 16 · FAIL 0 · ERROR 0 · SKIP 0 · MANUAL 0 · 耗时 57s
                                                     报告: runs/20261024_153506/report.html
npm run lint --workspace uitest|data_lineage|text2sql   -> eslint 零输出(通过)
npm run build --workspace uitest|data_lineage|text2sql  -> ✓ built
python scripts/check_workflow.py                  -> 见本报告提交后的输出(随本批次 commit 执行)
```

真浏览器核验(新代码实例跑在 7911 端口,chrome-devtools 驱动,截图在 runs/adhoc/batch_verify/):

| 票 | 实况 | 截图 |
| --- | --- | --- |
| 01 | Demo:write_config → "Success (version 3)",路径 configs\demo_fake_to_console.conf(cwd 内),总结与工具结果一致 | 01_demo_honest.png |
| 02 | EN 界面:testgen "Inferred types: …"、lineage "Lineage Governance Health Report"、orchestrator 降级英文描述 | 02a/02b/02c_*.png |
| 03 | History 新行全部带来源([ui]/[mcp]/[subscription] GMV日报),无空 Question | 03_history_dash.png |
| 04 | /mcp 表格 6 个 skew 工具描述齐全,无空单元格 | 04_mcp_descriptions.png |
| 05 | View 报告后 console 零 error(改前必现 Blocked script execution) | 05_uitest_report_clean_console.png |
| 06 | 粘贴 db_password = "SuperSecret123!" → medium Password assignment,预览 masked(Supe…3!) | 06_secretscan_db_password.png |

## 前后差异

- 测试:改前基线 3359 passed(含 1 个环境依赖失败隐患);改后 3360 passed + 新增 13 个回归/守卫用例(demo×2、i18n×4、qlog×1、mcp 描述×1、iframe×1、secretscan 正例 3 反例 2 计入参数化)。
- UI:
  - Demo 总结由"假成功"(修前实况见会话首轮巡检截图)→ 真实成功/失败(01_demo_honest.png)。
  - EN 界面三处中文 → 英文(02a/02b/02c)。
  - uitest 报告 console:1 个 Blocked error → 0(05)。
  - /mcp 空描述 6 处 → 0(04)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | lineage render.py 其余报告(链路/路径/SLA/impact)仍为中文 only(~60 处),EN 界面显示中文 | render.py 全文 grep [一-龥] | 本批次仅修巡检发现的 health 报告,整模块 i18n 超出票 02 范围 | EN 用户读其他 lineage 报告仍是中文 | 立专票做 render.py 全量 i18n(复用 _HEALTH_I18N 模式) |
| 中 | text2sql History 的"—"占位分支未在真浏览器见到(首屏全是新行) | 03_history_snapshot.txt 无 10-23 旧行 | 旧空行被新纪录翻出首屏 | 低(代码+构建已覆盖,分支极简) | 翻页功能上线后顺手复核一眼 |
| 低 | 巡检发现的 Gradio `@import rules are not allowed` console warning ×4 | 会话巡检 console 记录 | Gradio 6 自身样式注入 | 无功能影响 | 等 Gradio 上游修复,不动 |
| 低 | 7860 上用户长跑实例仍是旧代码 | 本批次未重启该进程 | 不打断用户会话 | 用户在 7860 看到的仍是修复前行为 | 用户方便时重启(`seatunnel-agent ui --build`) |

## 未执行的步骤

- 未重启用户 7860 实例(避免打断用户会话);全部真浏览器核验在 7911 新实例完成。
- `check_workflow.py` 在本报告落盘并提交后执行,输出见对话(报告文件无法包含晚于自身提交的输出,此为流程固有顺序)。
