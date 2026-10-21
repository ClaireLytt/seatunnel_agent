# 既有问题修复:text2sql lint 错误 + sql_review stats 页测环境依赖

Labels: `ready-for-agent`
Branch: `plat`(沿用:直接在 plat 开发提交,不切新分支)

## Problem Statement

两个既有问题让质量门禁失真:① text2sql workspace 的 src 有 6 个 eslint 错误(no-explicit-any ×5、rules-of-hooks ×1)+1 警告,`npm run lint` 对该 workspace 恒红,真回归会被噪音淹没;② test_sql_review_page 的 stats 刷新测试读到本机真实 review 历史(fixture 只打桩了写入端 ReviewLogger.log,没隔离读取端),凡本机用过 SQL Review 的环境跑全量 uitest 必红——测试结果取决于机器而非代码。

## Solution

① 修 text2sql src:给 5 处 any 补真实类型,把回调内的 hook 调用重构为符合 rules-of-hooks 的等价实现(行为不变);lint 恒绿。② 修 stats 页测隔离:fixture 把 review 历史的读取路径隔离到 tmp(经现有 env 变量;若 ReviewLogger 无路径 env 则按仓库 JsonlLog 惯例确认其开关/路径变量),测试在任何机器上确定性通过。

## User Stories

1. As a frontend maintainer, I want text2sql's lint to pass, so that the lint gate catches real regressions for this workspace again
2. As a developer, I want the five `any`s replaced with real types, so that the board/metrics/subscription views are type-checked
3. As a developer, I want the hook-in-callback refactored to a rules-of-hooks-compliant shape with identical behavior, so that React's invariants hold without changing what users see
4. As a developer, I want the stats page test to pass on any machine, so that full uitest runs are deterministic regardless of local review history
5. As a test author, I want the review-history read path isolated in the fixture, so that stubbing write and read are symmetric
6. As a reviewer, I want zero behavior change in production code paths (text2sql UI 行为、sql_review stats 端点逻辑), so that lint/pytest/build remain the complete regression

## Implementation Decisions

- text2sql:5 处 no-explicit-any 从调用处/API 响应形状推导真实类型(api 层已有类型定义可复用);MetricsView 的 useMetric 回调内调用改为提升到组件顶层或拆子组件(以改动最小、行为逐像素等价为准);1 条警告顺手消除
- sql_review 页测:fixture 将 review 历史读取路径指向 tmp(ReviewLogger 遵循仓库 JsonlLog 惯例,应有 PATH/LOG env 对;实施时以代码为准),删除对"写入端打桩即可"的错误假设;测试断言不变
- 不动 stats 端点本身与 ReviewLogger 实现;不扩大到其他 workspace 的 lint 清理
- 单批两票:T1 text2sql lint 修复;T2 stats 页测隔离;每票独立提交,批次一份报告

## Testing Decisions

- 缝全部既有:① `npm run lint --workspace text2sql` 恒绿 + `npm run build` 产物等价 + 既有 text2sql 页测/聊天 API 测试回归;② `pytest -m uitest tests/test_sql_review_page.py` 在"本机有真实 review 历史"的环境下通过(本机即天然复现环境)
- rules-of-hooks 重构的行为等价由 text2sql 页测(tests/test_t2s_page.py)与 build 守住;如 MetricsView 无页测覆盖,补一个最小断言(图表区可见)而非组件单测
- 全量验证:ruff/mypy/pytest、lint/build(text2sql)、uitest smoke、check_workflow.py

## Out of Scope

- 其他 workspace 的 lint 债(data_skew warning 等);stats 端点功能改动;chunk 体积警告
- main 操作、新分支、PR

## Further Notes

- 证据来源:C2 票06(stash 复原验证 lint 为 pre-existing;错误清单 BoardsView ×4、MetricsView:82、SubscriptionsView:51)与 C1 票04(stats 失败根因:fixture 只打桩 ReviewLogger.log,/stats 读到 2026-10-18~20 真实记录)
- 测试缝不新增,维持"接口即测试面"
