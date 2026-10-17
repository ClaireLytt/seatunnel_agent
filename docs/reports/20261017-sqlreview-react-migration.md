# 批次结果报告:SQL Review 页 React 迁移(tickets 01-06)(2026-10-17)

## 批准依据

> grill 共识后用户逐票批准:"implement"(确认 tickets 拆分并开始)、"确认OK，继续ticket 02"、"确认OK，继续ticket 03"、"确认OK，继续ticket 04"、"确认OK，继续ticket 05"、"确认ok 修改bug6"(即 ticket 06)。
> 方案共识(grill):完整 React 迁移对标 frontend/uitest;功能 1:1;router 无条件挂载;允许薄路由层(fix mode / line_links / stats 端点);验证通过后删旧 Gradio 页;不发 GitHub issue,tickets 落盘 `.scratch/sql-review-react/issues/`。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | React workspace 骨架 + static review 闭环 + router 无条件挂载 | frontend/sql_review/*、hub/ui.py、sql_review/manifest.py、tests/test_sql_review_page.py | 8d1d456 |
| 高 | Fix(static/LLM)/Clear/下载/DDL+规则折叠区;/fix 增 mode | frontend/sql_review/src/*、sql_review/api.py | 575eb99 |
| 高 | 行跳转(/review 增 line_links)+ URL 预填 + 跨页传 SQL | ReportView.tsx、App.tsx、api.py | 7116b84 |
| 中 | GET /stats 只读端点 + recharts 趋势图(替代 matplotlib) | api.py、TrendChart.tsx | 9125b51 |
| 中 | i18n 逐字平移机械核对 + 语言切换浏览器冒烟 | tests/test_sql_review_page.py | 54c002c |
| 高 | manifest external=True;删 ui.py + i18n UI-chrome key;清 css/uitest 死引用 | manifest.py、ui.py(删)、i18n.py、hub/css.py、ui_testing/{page,catalog}.py、cases/*.yaml、tests/* | (本批次提交) |

## 验证结果

```
ruff check src tests                      -> All checks passed!
mypy                                      -> Success: no issues found in 103 source files
pytest -q                                 -> 2975 passed, 1 skipped, 99 deselected (ticket 06 收尾全量)
pytest -m uitest tests/test_sql_review_page.py -> 4 passed (真浏览器:加载/审查/修复/折叠/清空/预填/行跳转/语言/倾斜桥)
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                                          -> PASS 83 · FAIL 0 · ERROR 0 · SKIP 2 · MANUAL 4 · 耗时 451s
                                             报告: runs/20261017_201953/report.html
python scripts/check_workflow.py          -> (见本报告提交后的批次收尾输出,附于对话)
```

## 前后差异

- 测试:全量 pytest 2970 passed(迁移前)→ 2975 passed;sql_review API 测试 303 → 311;新增真浏览器冒烟 4 条;uitest smoke 迁移后 PASS 83 / FAIL 0。
- UI 截图(docs/reports/shots/):
  - 迁移前(Gradio):`sqlreview_gradio_before.png`
  - 迁移后(React):`sqlreview_react_zh_light.png`、`sqlreview_react_en_light.png`、`sqlreview_react_zh_dark.png`
  - 对比点:engineering-paper 主题 + badge 头部对齐 uitest;无蓝紫渐变;报告/修复 SQL/统计趋势图均客户端渲染。

## 实施中的范围说明(与原 ticket 文字的差异)

1. ticket 06 原文"删除 Python i18n 字典"→ 实际仅删除 UI-chrome/动态消息 key(37 个×2 语言);`sr_cache_hit`/`sr_no_sql`/`sr_fix_no_sql` 与全部 CR 报告 key 为后端渲染所用(agent.py:107,138、fixer.py:73、report.py render_report),保留(i18n.py 剩 30 key×2,中英对称)。
2. uitest YAML 用例 SR1-SR13、SCR5、DSK17 退役(针对旧 Gradio DOM;先例 388a934),等价覆盖移至 tests/test_sql_review_page.py;catalog.py 移除 sqlreview agent 项;page.py 移除 /sqlreview READY、专属 LABELS 与 .sr-report-card 选择器。
3. 薄路由层三处均经 grill 批准:/fix mode=static(复用 autofix.apply_static_fixes)、/review line_links 透传、GET /stats。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | PostToolUse hook 指向不存在的 tools/ui_check_hook.py,每次 Write/Edit 报错 | .claude/settings.json:67-80;tools/ 目录不存在 | 配置残留或文件丢失 | 会话噪音,掩盖真实 hook 失败 | 删配置或补文件(retro 已呈报,待圈选) |
| 中 | coverage 测试仍硬编码具体用例 id("DAG1") | tests/test_ui_testing.py test_counts_and_statuses | 迁移时顺手替换,未根治 | 下个页面迁移再踩 | 改结构性断言 |
| 低 | ccmetr 启动器硬编码 python3,Windows 无此命令 | .claude/ccmetr/bin/ccmetr:7 | 启动器未做回退 | attach 需手动绕过 | 加 python 回退 |
| 低 | 前端 eslint/prettier 存在但未接入验证命令/CI | frontend/*/package.json scripts;CLAUDE.md 第 8 节无此项 | 守护缺口 | React 代码仅靠 tsc 把关 | 第 8 节加 npm run lint |
| 低 | /transpile、/dataskew 仍为 Gradio,localStorage 桥接方向为 React→Gradio | manifest 未 external | 不在本批范围 | 风格不一致延续 | 后续按 docs 先例迁移 |

## 未执行的步骤

- GitHub issue/tickets 未发布到 tracker:用户明确"不要发 issue",spec issue #123 已按用户要求关闭,tickets 落盘 `.scratch/sql-review-react/issues/`。
- LLM 模式 review/fix 的端到端真调用未在自动化中执行(测试均 monkeypatch 或走 static;与迁移前一致,API 核心逻辑未改动)。
