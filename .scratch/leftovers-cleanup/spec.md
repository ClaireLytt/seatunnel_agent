# 遗留清单清零:紫色卡片、data_skew 警告、chunk 体积、截图副产物

Labels: `ready-for-agent`
Branch: `plat`(沿用:直接在 plat 开发提交,不切新分支)

## Problem Statement

各批次报告累计的剩余遗留项:① orchestrator(#7c3aed)与 issue_triage(#9333ea)的 hub 卡片颜色违反"禁蓝紫"UI 规范;② data_skew src 有 1 条 react-refresh lint 警告,门禁不是零噪音;③ 带 recharts 的 workspace(llm_eval/llm_cost 等)及 change_impact/data_comparison/data_lineage/text2sql 构建时报 chunk >500kB 警告;④ seatunnel/docqa/webtask/llmcost 等页测每次运行会重写 docs/reports/shots/*.png(像素微差),污染工作区,本轮已多次手动还原。

## Solution

一次清零:① 两张卡片换为合规且不与现有卡片撞色的暖色系(orchestrator→深橙红、issue_triage→青绿系,实施时对照现有 25 卡配色表选不重复值);② 修 data_skew 警告;③ shared vite 基座加可选 manualChunks(把 recharts/react 大依赖拆 vendor chunk)并将警告阈值调整为诚实值,所有 workspace 受益,构建零警告;④ 页测截图输出改到 runs/ 下临时目录,报告中的正式对比截图维持 docs/reports/shots/ 为手动产物,不再被测试覆写。

## User Stories

1. As a platform user, I want every hub card color to comply with the no-blue-purple rule, so that the visual language is consistent
2. As a platform user, I want the two recolored cards distinguishable from the other 23 cards, so that scanning the hub stays easy
3. As a frontend maintainer, I want zero lint warnings across all 25 workspaces, so that any new warning is signal
4. As a frontend maintainer, I want big third-party deps split into vendor chunks via the shared vite base, so that build output has no size warnings and page loads cache vendors across visits
5. As a developer, I want page-test screenshots written under runs/ instead of docs/reports/shots/, so that running tests never dirties the working tree
6. As a reviewer, I want the curated before/after comparison shots in docs/reports/shots/ to stay as committed artifacts, so that past batch reports keep their evidence
7. As a reviewer, I want zero behavior change beyond colors, so that lint/build/pytest remain the complete regression

## Implementation Decisions

- 卡片换色:只改两个 manifest 的 color 字段;新色从暖色/中性系选且与现有卡色值去重(实施时列出 25 卡现值表作证据);截图 hub 首页入报告供用户过目,用户不满意再改一次即可
- data_skew 警告:按 react-refresh 规则要求调整导出结构(通常是非组件导出分文件),行为不变
- chunk 拆分:shared vite.base 的 makeViteConfig 增加内置 manualChunks(react/react-dom/recharts 入 vendor)或按需参数;25 个 workspace 全量重建验证产物可服务(抽页测);不设 chunkSizeWarningLimit 掩盖——以真实拆分消除警告为准,拆不掉的如实保留并记录
- 截图输出:页测中的 SHOTS 常量改指 runs/shots/(或 tmp),涉及的页测文件统一改;docs/reports/shots/ 现有 PNG 不动(历史报告证据);后续批次报告的"正式对比截图"由人为复制入 docs(写入 react_migration.md 一句约定)
- 单批四票:T1 换色+hub 截图、T2 data_skew 警告、T3 manualChunks、T4 截图输出迁移;T1 与 T2/T3/T4 文件不相交可并行,T4 收尾出批次报告

## Testing Decisions

- 缝全部既有:lint/build(25 workspace)、全量 pytest、`-m uitest` 页测抽样、uitest smoke;换色由 hub 首页截图人工过目(AIP1 用例断言卡片存在,不断言颜色)
- manualChunks 后抽 3 个页测(含 recharts 页 llmeval/llmcost)验证 dist 可服务
- 截图迁移后跑两个原本重写 PNG 的页测,确认 git status 干净即验收

## Out of Scope

- 其他配色调整;recharts 版本升级;docs/reports/shots 历史清理
- main 操作、新分支、PR

## Further Notes

- 换色是设计决策:spec 默认我选合规色并截图供过目,用户可一票否决重选(避免再开一轮问答)
- 证据来源:各批次报告遗留清单(紫色 ×2、data_skew warning、chunk 警告、截图副产物多次 git checkout 还原)
