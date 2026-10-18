# Spec: Data Skew Analyzer React 迁移

Label: ready-for-agent

## Problem Statement

用户在 hub 的 `/dataskew` 页做 SQL 倾斜分析（静态/LLM、连库实测探针、一致性
实测、SeaTunnel split-key、运行时事件日志分析、历史记录），但该页仍是 Gradio
实现（ui.py 881 行、8 个功能区），与已迁移的 9 个 React 页不一致，是剩余
Gradio 页中最重的一个。

## Solution

按 docs/react_migration.md 触点清单，以 uitest 骨架 + sql_transpile/
data_comparison 先例迁移为 React，cutover 后退役 Gradio 页及触点。

**关键决策**（grilling 已确认）：
- **连接会话层**：照搬 data_comparison 的 per-session connection registry
  模式（X-Session-Id 头 + 服务端 executor/ProbeCache 注册表）；连接预设复用
  现有共享 `ConnectionPresetsStore`。
- **上传/下载轻量路线**：SQL/conf 上传纯前端读文件填框；报告 .md/优化 .sql/
  补丁 conf 下载用前端 Blob；仅 Spark 事件日志走 multipart 端点。
- **LLM 分析保持阻塞**：POST + busy 态，无 SSE；LLM 不可用回退静态 + banner。
- 双桥接保留：localStorage `st_dataskew_sql` pickup + `st_dataskew_conn`
  cookie 连接预填（无密码）。
- 全程 `ui-build-incremental` 串行开发，不建新分支/worktree；4 票串行。

## User Stories

1. 作为数据工程师，我想粘贴/上传 SQL、选方言（spark/maxcompute/hive）与模式（static/llm）点"开始分析"，得到倾斜分析报告；llm 模式额外产出优化 SQL（代码块）。
2. 作为数据工程师，我想 LLM 不可用时自动回退静态分析并看到说明 banner。
3. 作为数据工程师，我想下载报告 .md 与优化 .sql（分析后出现）。
4. 作为数据工程师，我想展开"连接数据源"（支持预设读取、`st_dataskew_conn` cookie 预填）连接 hive/sparksql/mysql/postgresql/sqlite，选采样比例，对分析出的倾斜点做"验证倾斜（实测）"，探针结果追加进报告。
5. 作为数据工程师，我想有优化 SQL 时做"一致性实测"（原/优化 SQL 对比跑），结果追加进报告；无优化 SQL 时得到提示。
6. 作为数据工程师，我想粘贴/上传 SeaTunnel conf 做 split-key 检查，最佳 key 不同时可下载补丁后的 conf。
7. 作为数据工程师，我想上传 Spark 事件日志或填 History Server URL + app id 做运行时倾斜分析。
8. 作为数据工程师，我想刷新/载入分析历史（最近 20 条，JSONL 存储）。
9. 作为 sql_review/data_comparison 用户，我想"送到 dataskew"后 SQL 自动预填、连接信息自动带入表单。
10. 作为中文/英文用户，我想 zh/en 全文案切换、暗色模式正确。
11. 作为 API 用户，我想现有 `POST /api/skew/check`、`GET /health` 契约不变，新增端点向后兼容。
12. 作为维护者，我想有 Playwright 页测（DSK1-DSK21 等价）与 i18n parity 测试；旧 YAML/catalog/page.py/css.py 触点干净清理。

## Implementation Decisions

- 新端点（prefix /api/skew，全部结构化错误、目录/路径类入参白名单）：
  analyze（static/llm + probe_context）、connect/disconnect/status（会话注册
  表）、verify（探针）、consistency、splitkey（响应含补丁 conf 文本）、
  runtime/eventlog（multipart）+ runtime/history-server、history list/load、
  presets list/get（代理共享 store，密码仅在 get 单条时返回——与 Gradio 行为
  一致）。
- 会话注册表照 datacompare：TTL 清理、X-Session-Id 由前端生成保存
  sessionStorage。
- workspace `data_skew`（目录名 = manifest.name），vite base `/dataskew/`；
  复用 SqlView/ReportView 先例；折叠区结构与 Gradio 一致。
- 报告"追加 section"逻辑（probe/CST 替换同名段）移到服务端 analyze/verify/
  consistency 响应中返回完整报告文本，前端只渲染。
- manifest 切 external、hub 无条件挂 router、_DATA_API_NAMES 移除 data_skew。

## Testing Decisions

- 缝：Playwright 页面层（先例 test_transpile_page.py；连库用例用
  config/uitest_demo.db SQLite fixture 等价）、REST 契约层（test_data_skew.py
  既有 API 测试保持 + 新端点定向测试）、i18n 资产层（先例
  test_transpile_i18n.py）。
- DSKA1（真 LLM）不进自动化；LLM 路径以"无 key 回退 static"确定性覆盖。
- 桥接/cookie 预填：页测先种 localStorage/cookie 再加载断言。

## Out of Scope

- detector/probe/consistency/splitkey/runtime/history 核心逻辑改动；
  其他页迁移；新功能（SSE、图表等 Gradio 版没有的）。

## Further Notes

- 票据 4 张见 issues/；01 先把 API 缝做实，02/03 前端分两刀，04 收尾。
- before 截图须在退役前截取；hub/css.py 的 dsk 相关段退役时清理（吸取
  transpile 批次 .st-trp-* 漏删教训）。
