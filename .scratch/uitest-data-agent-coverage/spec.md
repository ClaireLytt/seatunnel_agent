# Spec: data 工作区 UI 测试按钮级覆盖补全

Labels: `ready-for-agent`

## Problem Statement

作为维护者,我依赖 UI 测试(uitest yaml + Playwright page tests)来保证 data 工作区 18 个页面在改动后不回归。但按钮级盘点显示覆盖并不完整:15 个 React 页中,主流程按钮基本覆盖,而大量次要控件从未被测试点击过 —— 全仓库没有任何 `expect_download`(所有下载按钮只断言可见)、约 8 个页面的方言下拉从未切换过、data_comparison 的 8 个特性 run 按钮一个没点过、text2sql 的大量视图级按钮(反馈、导出、订阅启停等)未测。这些控件坏了测试不会红,只能靠人工发现。

## Solution

在现有 Playwright page tests 这一层补齐按钮级覆盖:为每个有缺口的页面追加确定性(零 token)测试用例,让"页面上每个可交互控件至少被一条测试真实触发一次",下载类控件用 `expect_download` 真点真收文件。不引入新测试框架、不改前端代码(除非测试暴露真 bug)。

## User Stories

1. As a 维护者, I want 每个下载按钮都被 `expect_download` 真实点击并校验文件名/非空内容, so that 下载链路坏掉时测试会红而不是只看按钮可见。
2. As a 维护者, I want 每个页面的方言下拉至少切换一次非默认值并跑通主流程, so that 方言参数传递回归能被捕获。
3. As a 维护者, I want data_comparison 的 count/sample/aggregate 核心动作按钮被真实点击并断言结果卡片, so that 四个核心对比动作都有回归保护。
4. As a 维护者, I want data_comparison 的 8 个特性手风琴 run 按钮(incremental/quality/skew/checksum/chunked/partition/customAgg/sql)各被点击一次, so that 特性面板的请求与渲染不悄悄坏掉。
5. As a 维护者, I want data_comparison 的 GenerationCard 四个按钮(生成同步配置/Diff SQL/血缘/环境对比)与 sync 配置下载链接被测试, so that 生成类功能有覆盖。
6. As a 维护者, I want data_comparison 的 ReportsCard(save/refresh/load/diff)、Templates 的 delete 与批量运行、Trend show、Schedule start/stop、Preset B 侧保存被测试, so that 报告/模板/趋势/调度闭环可回归。
7. As a 维护者, I want data_comparison 的 Export CSV/Excel/独立报告链接被真实触发校验, so that 导出链路有保护。
8. As a 维护者, I want text2sql 聊天区的 Enter 发送、Stop、上一页、CSV 下载、PNG 导出、👍/👎 反馈被测试, so that 聊天交互的每个控件都有覆盖。
9. As a 维护者, I want text2sql 的 History(refresh/qlog CSV/delete-selected/resume)、Favorites(rename/delete/refresh)、Metrics(行展开/use metric)、Boards(render/delete/refresh)、Subscriptions(create/启停/run-now/delete)与模板 chip 被测试, so that 各 hash 视图的按钮都有回归保护。
10. As a 维护者, I want text2sql Schema 面板的 select-all 与 reload 按钮被测试, so that 表过滤交互完整可回归。
11. As a 维护者, I want data_skew 的分析模式下拉(static/llm 中可确定性测的部分)、split-key 上传 conf 与下载 patched conf、Runtime 面板(rt_btn/文件上传)、连接预设 load、采样大小下拉、Copy SQL 被测试, so that 数据倾斜页全部面板可回归。
12. As a 维护者, I want data_lineage 的方向下拉切换(仅上游/仅下游)、Copy mermaid 源、path 路径分析按钮、Agent 真实提问路径被测试, so that 血缘页高级功能有覆盖,并可退役过时的 LIN13 yaml 用例。
13. As a 维护者, I want sql_review 的 → Transpile 跨页按钮、Download Report 真下载、Stats Refresh 被测试, so that 审查页全部出口可回归。
14. As a 维护者, I want sql_transpile 的源方言下拉(非 auto)切换与 Copy SQL 被测试, so that 翻译页控件齐全。
15. As a 维护者, I want config_migrate 的复制到剪贴板按钮被测试, so that 迁移结果可复制功能有保护。
16. As a 维护者, I want 剪贴板类按钮(copy)用 Playwright clipboard 权限断言写入内容, so that 复制功能坏掉能被发现。
17. As a 维护者, I want 新增用例全部为确定性(--no-llm/零 token)用例, so that CI 不产生 LLM 费用且结果稳定。
18. As a 维护者, I want 一份覆盖对照清单落在报告中(控件 → 测试函数), so that 下次盘点有基线。

## Implementation Decisions

- **不新增测试层(seam)**:全部补测落在现有最高层 seam —— Playwright 真浏览器 page tests(pytest `uitest` marker,复用现有 `tests/test_*_page.py` 的 fixture:构建后的 hub 静态挂载 + sqlite demo 数据)。不碰 uitest yaml runner(它只负责余下 3 个 Gradio 页,本次不扩)。
- 每个页面的补测追加到对应的既有 `test_<page>_page.py` 文件,沿用其连接/填充 helper;不新建文件,除非该文件超出可维护长度。
- 下载断言统一用 `page.expect_download()`,校验 `suggested_filename` 与内容非空;客户端 blob 下载同样走此 API。
- 剪贴板按钮用 browser context `permissions=["clipboard-read","clipboard-write"]` + `navigator.clipboard.readText()` 断言。
- LLM 依赖按钮(data_skew llm 模式、lineage Agent 真实提问、transpile LLM advice 已测)只测确定性可达部分:无 key 时的降级提示文案,不调真模型。
- data_lineage 补测落地后,删除 `extended.yaml` 中指向 Gradio /lineage 的 LIN13(页面已 React 化,该用例测的是退役路由)。
- 不修改任何前端源码;测试若暴露真实 bug,单独上报等用户圈选,不顺手修。
- 批次划分(每批独立可验收):批次1=下载+剪贴板横切真测;批次2=data_comparison 补点;批次3=text2sql 补点;批次4=data_skew + data_lineage;批次5=长尾(sql_review/transpile/config_migrate/方言切换横切)。

## Testing Decisions

- 好测试 = 只断言外部行为:点击控件后用户可见的结果(结果卡片出现、下载文件名正确、剪贴板内容、提示文案),不断言组件内部 state 或请求细节。
- 被测模块:`frontend/` 下 15 个 data 工作区 React workspace 的构建产物,经 hub 挂载后在真浏览器中测。
- 先例:`tests/test_datacompare_page.py`(SSE 流式断言、accordion 交互)、`tests/test_dataskew_page.py`(文件上传、cookie/localStorage 桥)、`tests/test_sql_review_page.py`(expect_popup 跨页)。新用例照这些模式写。
- 验证命令:`pytest -m uitest -k <page>` 定向跑 + 批次收尾全量;照第 8 节另跑 ruff/mypy。

## Out of Scope

- 3 个 Gradio 页(/dagcheck /loginspect /mcp)的 yaml 用例扩充(现有 DAG/LGI/MCP 覆盖维持现状)。
- 前端功能修改、UI 重构、新控件。
- LLM 真调用路径的端到端测试。
- shared 顶栏(导航/语言/主题切换)控件 —— 属于 hub 横切,不在 data agent 范围。
- ai / devops 工作区页面。

## Further Notes

- 盘点基线:前端控件清单与测试交互清单来自 2026-10-19 的两次全量扫描(frontend/*/src 与 tests/test_*_page.py),对照结论见会话报告;若前端在落地前有改动需重扫差异。
- data_quality 包无 manifest、无 UI 页面,无需 UI 覆盖。
