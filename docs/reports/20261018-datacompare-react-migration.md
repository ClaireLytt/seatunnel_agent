# 批次结果报告:datacompare-react-migration(2026-10-18)

## 批准依据

> 用户 grilling 答复:「1-6都要,先ship当前分支」→ 修订为「只要1-4 并且还在当前分支就可以」(该轮针对 sqlreview);datacompare 轮答复:「1-2yes 3继续在现分支」;
> 随后依次调用「/to-spec」「/to-tickets」「/implement-spec」启动 11 票实现;
> 票 11 中断后用户明确:「重新派票11继续完成」、「继续」。

## 已完成

| 优先级 | 内容 | 票 | commit |
| --- | --- | --- | --- |
| 高 | 预重构:会话级连接注册表 + 卡片模块 Gradio-free 验证 | 01 | fa2017b |
| 高 | REST connect API + React 骨架接管 /datacompare(manifest 翻转) | 02 | 2d76da0, 4f9c86a |
| 高 | 核心动作 schema/count/sample/aggregate(服务端 HTML 卡片) | 03 | 5b86630, 98015be |
| 高 | 复合动作 SSE 进度 + 409 防重入 | 04 | c811708 |
| 中 | 全局选项 + 连接预设 CRUD | 05 | 34e8099 |
| 中 | 7 个分析手风琴(增量/质量/倾斜/校验和/分区/自定义聚合/自定义 SQL)+ compare-all 可选段接线 | 06 | 263f4fc, 8011d49, 31552c8 |
| 中 | 报告保存/列表/加载/diff、CSV+Excel 导出、独立报告页 | 07 | 72b99fe |
| 中 | sync-config/diff-SQL/lineage/多环境/模板批量 | 08 | 2996930 |
| 中 | 调度 + webhook + recharts 趋势(修复 legacy 定时保存 arity bug) | 09 | 3cfc78d |
| 中 | i18n 全量对齐(zh/en)+ 暗色截图 | 10 | 35fe5cb |
| 高 | 退役:删 ui.py(2602 行)、清 107 死键、删 25+ YAML case、死 CSS、indigo 重着色 | 11 | 7a1c264, a44fa77, 000567a, 96f658e, 7320a7b |
| 中 | Code-review 修复批(11 项发现:9 修复 2 接受) | — | 2cd4573, 02698f4 |
| 中 | `seatunnel-agent ui --build` 一步构建+启动 | — | 1324ebf |
| 高 | workspace 目录名对齐 manifest.name(挂载落空修复) | — | 615482a |

## 验证结果

```
ruff check src tests                                 -> All checks passed!
mypy                                                 -> Success: no issues found in 114 source files
pytest -q                                            -> 3128 passed, 1 skipped, 88 deselected in 136.18s
pytest -m uitest tests/test_datacompare_page.py      -> 8 passed in 41.91s
python -m ...ui_testing run --suite smoke --no-llm   -> PASS 60 · FAIL 0 · ERROR 0 · SKIP 0 · MANUAL 1 · 耗时 256s
npm run lint --workspace data_comparison             -> clean (eslint src)
npm run build --workspace data_comparison            -> ✓ built in 9.53s
python scripts/check_workflow.py                     -> 三项 PASS(见下)
```

## 前后差异

- 测试:main 起点 2979 → 3128 passed;datacompare 专属新增 ~190 个 API/注册表/i18n/页面测试;YAML 引擎 datacompare case 由 Playwright/API 测试替代。
- UI:`docs/reports/shots/datacompare-gradio-before-{light,dark,zh}-full.png`(e6d0e75 旧页)vs `datacompare-react-{light,dark}[-zh]-full.png`(新页)。
- 代码:遗留 UI 层 ~4200 行删除;逻辑层(comparator/presets/templates_store 等)零改动;新增 REST 层 8 模块 + React workspace。

## Code-review 发现与处置(中途评审,固定点 e6d0e75)

| 发现 | 处置 |
| --- | --- |
| `_get_session` 五处复制 | 修复:deps.py 单一 get_session_or_404(2cd4573) |
| option 字段块跨 model 重卷 | 修复:OptionsRequest/SessionTablesRequest 基类(2cd4573) |
| 400/422 口径不一 | 修复:统一 422(2cd4573) |
| 注册表永不回收(泄漏) | 修复:cap=100 + 最老淘汰,调度会话豁免(2cd4573) |
| 调度 tick 绕过 409 防重入 | 修复:共享 running guard(2cd4573) |
| 模板丢 watermark/quality 字段 | 修复:双向接线 + 回归测试(02698f4) |
| 选项重置缺 ~8 个目标 | 修复:对齐 legacy 27 目标清单(02698f4) |
| Tab 填充占位符缺失 | 修复:tabFill.ts 1:1 移植(02698f4) |
| 趋势图合并 legacy 两子图 | 接受:展示性偏差,代码注释记录 |
| App.tsx 5-prop 捆 ×6 卡片 | 接受:达阈值但不重构,留待后续 |

## 有意的 1:1 偏离

1. legacy `_schedule_tick` 调 `_save_report` 参数错位,定时比对从未真正保存报告(被吞 TypeError)——迁移时修复(schedule_api.py 文档注明)。
2. 定时运行现可携带可选分析段(legacy 调度只传 where/key/threshold/webhook)。
3. 多环境卡与模板卡头部 indigo `#6366f1` → `var(--ink)`(UI 规范,禁蓝紫)。
4. YAML 覆盖断言(75 项人工清单 auto>=55)退役:清单是 Gradio 页验收矩阵,职责移交 React 测试套件(test_ui_testing.py 注释与本报告记录)。

## 遗留问题清单

| 问题 | 证据 | 原因 | 影响 | 优先级 | 建议 |
| --- | --- | --- | --- | --- | --- |
| t2s_examples.json pytest 写回漂移根治未做 | pitfalls.md 2026-10-17/18 两行;本批又回退 1 次(f2bc433) | 示例库路径在仓库内 | 每次全量测试脏工作区 | 中 | 测试 fixture 重定向 T2S_EXAMPLES_PATH 到 tmp_path |
| uitest engine 残留已退役页引用 | page.py:234 `"/text2sql": ".st-sidebar-status"`;page.py:479-651 的 .st-main 选择器仅服务已退役 Gradio 页 | 逐页迁移遗留 | 死代码,误导维护者 | 低 | 专项清理 engine 的 React 时代选择器映射 |
| catalog.py 的 text2sql 旧条目 | 自 sqlreview 批报告遗留 | 同上 | 低 | 低 | 随上一条一并清理 |
| hub css 通用布局类(.st-page-row/.st-sidebar/.st-main)已无 Gradio 页渲染 | 本批 grep:仅 engine 断言引用 | datacompare 是最后使用者 | 死 CSS | 低 | 与 engine 清理同批删除 |
| coverage.py 与 dc_test_checklist.html 为历史 PRD 工件 | counts auto==0(test_ui_testing.py 注释) | Gradio 验收矩阵退役 | 无功能影响 | 低 | 保留为历史文档或归档 |

## check_workflow 输出

```
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘(收尾提交附带本报告)
```
