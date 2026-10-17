# 批次结果报告:sqlreview-ui-align(2026-10-18)

## 批准依据

> 用户圈选对齐清单:「1-6都要,先ship当前分支」,随后改为:「只要1-4 并且还在当前分支就可以」;
> 随后用户调用 `/to-spec`、`/to-tickets`、`/implement-spec` 启动实现。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | TrendChart 严重级配色改主题 token(critical→accent / risk→ink-soft / suggestion→ok),暗色可读 | frontend/sql_review/src/components/TrendChart.tsx | f585c21 |
| 中 | 报告区空状态不渲染(对齐 uitest),删 reportPlaceholder 双语键 | frontend/sql_review/src/App.tsx, i18n.ts | f585c21 |
| 中 | 评审错误与统计错误渲染时加 ❌ 前缀;reviewFailed/rulesInvalid 字符串内嵌 ❌ 移除避免双写 | frontend/sql_review/src/App.tsx, i18n.ts | f585c21 |
| 低 | "SQL" 标签入 i18n(双语同值) | frontend/sql_review/src/App.tsx, i18n.ts | f585c21 |
| 中 | 新页测试:评审前报告区不存在(TDD 红→绿) | tests/test_sql_review_page.py | f585c21 |
| 中 | 评审修复:seatunnel 页 connectFailed 的 ❌ 从 i18n 字符串移到渲染时,三页约定统一;i18n 对照测试同步 | frontend/seatunnel/src/App.tsx, i18n.ts, tests/test_seatunnel_i18n.py | 本批收尾 commit |

## 验证结果

```
ruff check src tests                               -> All checks passed!
mypy                                               -> Success: no issues found in 105 source files
pytest -q                                          -> 2998 passed, 1 skipped, 105 deselected, 2 warnings in 116.60s
pytest -m uitest tests/test_sql_review_page.py     -> 5 passed in 24.48s
pytest -m uitest tests/test_seatunnel_page.py      -> 5 passed in 24.35s
pytest -q tests/test_seatunnel_i18n.py             -> 5 passed in 0.17s
npm run lint --workspace sql_review-frontend       -> clean
npm run build --workspace sql_review-frontend      -> ✓ built in 9.68s
npm run lint --workspace seatunnel                 -> clean
npm run build --workspace seatunnel                -> ✓ built in 3.02s
python scripts/check_workflow.py                   -> 见本批收尾 commit(三项 PASS)
```

## 前后差异

- 测试类:页面测试 4→5(新增空状态断言);全量 2998 passed 不变(i18n 对照测试期望同步更新)。
- UI 类:docs/reports/shots/sqlreview-align-before-{light,dark}.png vs sqlreview-align-after-{light,dark}.png(图表色从硬编码红/琥珀/绿变为主题 token,暗色下正确反色;报告空卡消失)。

## Code-review 发现与处置

| 发现 | 轴 | 处置 |
| --- | --- | --- |
| 主检出 dist 过期导致新页测试 FAIL | Spec | 已修:重建 sql_review-frontend dist,5 passed(见上) |
| after 截图证据链(与在盘 dist 不符) | Spec | 已修:新 dist 重拍,输出与已提交截图字节一致,证据链闭合 |
| 本批次无落盘报告(§7.6) | Standards | 已修:本文件 |
| ❌ 约定跨页不一致(seatunnel 烤在 i18n) | Standards | 已修:移到渲染时,双语键去前缀,对照测试更新 |
| ❌ 字面量跨 workspace 重复,未抽共享 helper | Standards(判断) | 接受:3 处跨 workspace,抽 shared 组件血radius大于收益,待第 4 处出现再抽 |
| risk→ink-soft 的警示语义弱于旧琥珀色 | Standards(判断) | 接受:与 uitest 色彙一致优先;主题无 warning token,新增 token 超范围 |
| sqlLabel 双语同值 | Standards(判断) | 接受:与 dialect 标签同一约定 |
| shoot.py 提交进 .scratch | Spec(轻微) | 接受:截图可复现性价值大于整洁 |

## 遗留问题清单

| 问题 | 证据 | 原因 | 影响 | 优先级 | 建议 |
| --- | --- | --- | --- | --- | --- |
| dist 为 untracked,代码改动后主检出需手动重建,否则页面/测试用旧产物 | 本批 code-review 实跑 1 failed;20261017 /seatunnel "not built" 同根因 | 构建产物不进 git(先例约定) | 本地验证可能误判 | 中 | 在 react_migration.md 增补"改前端后必须重建 dist 再跑 uitest"一条;或 pytest fixture 校验 dist mtime 晚于 src |
| sqlreview agent 模式无流式进度、无单次评审历史(对齐清单 5、6) | 比对报告第 8、9 条 | 用户圈选仅 1-4 | 慢评审无反馈;无法回看历史报告 | 低 | 后续独立 spec(用户已知悉) |
| t2s_examples.json pytest 写回漂移(根治) | docs/pitfalls.md 记录 | T2S 示例库写回仓库内路径 | 每次全量 pytest 产生脏文件 | 中 | tmp_path 隔离(待圈选) |
