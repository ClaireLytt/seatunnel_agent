# Spec: Data Lineage React 迁移

Label: ready-for-agent

## Problem Statement

用户在 hub 的 `/lineage` 页做数据血缘分析（从 SQL 目录 / SeaTunnel 配置 /
Hive 元数据建图，查询表/字段血缘、搜索、路径、SLA 影响、治理体检、快照
对比、LLM 血缘问答，Mermaid 图可点击节点跳转），但该页仍是 Gradio 实现
（ui.py 732 行、7 功能区），与已迁移的 11 个 React 页不一致。

## Solution

按 docs/react_migration.md 触点清单，以 uitest 骨架 + data_skew（最重先例）
迁移为 React，cutover 后退役 Gradio 页及触点。`/impact` 为同包独立 manifest
页，**不在本批范围**；清理共用触点（css/page.py）时必须保住 /impact。

**关键决策**（grilling 已确认）：
1. **图状态走会话注册表**（skew 模式）：`POST /build` 建图存会话（返回
   stats + 表清单），query/search/path/sla/health/snapshot 带 session_id
   复用已建图；现有无会话端点契约不动。
2. **Mermaid 用官方 npm 包**本地渲染（替代 iframe+CDN），节点点击客户端
   直接重查（替代 iframe 跳桥）。
3. **Agent 问答走 SSE** 新端点（@shared/sse.ts 先例）流式输出
   step/tool_call/text_delta 进度；阻塞 `/analyze` 保留。
4. 补齐缺口端点：build、search、GET snapshots、SLA 响应带链路 mermaid。
5. 目录入参沿用 `LINEAGE_API_ALLOWED_DIRS` 白名单（REST 原有）。

**流程约束**：全程在 `ui-build-incremental` 分支串行开发，不建新分支/worktree。

## User Stories

1. 作为数据工程师，我想填 SQL 目录（+方言）或 SeaTunnel 配置目录、可选启用 Hive（高级项：元数据表、分区），点"构建血缘图"看到图规模统计，目标表/路径终点下拉被填充。
2. 作为数据工程师，我想选表、方向（both/upstream/downstream）、深度（1-10 滑杆）、可选字段，点"查询血缘"得到可点击的 Mermaid 图 + Markdown 报告 + 可复制的 Mermaid 源（折叠）。
3. 作为数据工程师，我想点击图中节点直接跳转查询该表的血缘。
4. 作为数据工程师，我想模糊搜索表名得到相近候选。
5. 作为数据工程师，我想查两表路径、做 SLA 延迟影响分析（小时数输入）并看到链路图、跑治理体检报告。
6. 作为数据工程师，我想保存血缘快照、从快照列表选择并对比差异。
7. 作为数据工程师，我想用自然语言提问血缘问题并**流式**看到 agent 进度与回答，回答可能携带新图。
8. 作为数据工程师，我想空目录/坏目录/未建图/缺表名等得到本地化提示（结构化 {code,message}），超出白名单的目录得到 403。
9. 作为中文/英文用户，我想 zh/en 全文案切换、暗色模式正确（~55 个 i18n 键原样搬）。
10. 作为 API 用户，我想现有 /query /path /sla_impact /check /snapshot /snapshot_diff /analyze /impact /health 契约不变，新端点向后兼容。
11. 作为 /impact 页用户，我想该 Gradio 页在本批迁移后原样可用（共用 CSS/选择器不被误删）。
12. 作为维护者，我想有 Playwright 页测（LIN1-LIN11 等价；LIN12 真 LLM 留手动，SSE 路径以无 key 确定性覆盖）与 i18n parity 测试；lineage YAML、catalog、page.py READY/标签、css.py lineage 专属段被干净清理。

## Implementation Decisions

- 会话注册表照 data_skew（capped + idle TTL + 线程锁），持有已建 LineageGraph；
  POST /build 入参 = 源配置（目录白名单前置、结构化错误），响应 = stats +
  tables + session_id 绑定；带 session 的查询端点在会话缺图时返回结构化
  need_graph 提示。
- 新端点薄包装既有 graph 方法（search/list_snapshots/SLA chain mermaid），
  零核心改动；SSE 问答端点复用 EventCollector 事件流。
- workspace `data_lineage`（目录名 = manifest.name），vite base `/lineage/`；
  mermaid npm 依赖锁定版本；节点点击经 mermaid 回调绑定。
- manifest 切 external、hub 无条件挂 router、_DATA_API_NAMES 移除
  data_lineage（/impact 的 change_impact manifest 原样）。
- css/page.py 清理只删 lineage 专属项（.st-lin-hidden、READY /lineage、
  lineage 标签映射），共用 `.st-lin-*,...st-imp-*` 组合选择器改写为仅
  /impact 所需形式。

## Testing Decisions

- 既有缝：Playwright 页面层（先例 test_dataskew_page.py；demo 数据
  examples/lineage_demo）、REST 契约层（既有 test_data_lineage.py 等全部
  保持 + 新端点定向测试）、i18n 资产层（先例 test_dataskew_i18n.py）。
- SSE 问答页测走"未配 key"确定性路径；真 LLM 质量不进自动化。
- 不依赖 gitignore 文件；目录用 examples/lineage_demo（已入库）。

## Out of Scope

- /impact 页迁移；loaders/graph/render/agent 核心逻辑改动；OpenLineage 等
  后端能力;新功能。

## Further Notes

- 票据 4 张见 issues/；before 截图须在退役前截取；/impact 回归（IMP 用例
  在 smoke 中）作为收尾验证的一部分。
