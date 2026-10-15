# 血缘分析工作指南

## 数据来源与语义

1. **Hive 元数据表**（`zz.dwm_meta_table_lineage_df`，按 `pt` 分区，默认最新分区）：
   `relation_*` 列**只记录下游血缘**（当前表 → relation 表）；上游查询由工具的
   反向索引自动完成，你不需要自己反推方向。
2. **本地 SQL 文件**：基于正则的静态解析，覆盖 INSERT INTO/OVERWRITE 与 CTAS。
   子查询、UNION 等复杂写法的字段级血缘可能缺失（会降级为表级，见下）。
3. **SeaTunnel 配置文件**（*.conf/*.config/*.json）：解析 source/sink 块的
   table_name / database / query 等键，得到 source 表 → sink 表的同步血缘
   （仅表级，无字段级）。会话指定了 SeaTunnel 目录时可用
   `load_lineage_from_seatunnel` 加载。

## 展示规范（重要）

- 最终展示一律使用中文字段名：类型 / 库名 / 表名 / 表分层 / 是否在SLA /
  SLA产出时间 / 所在基线。
- 表分层按 ods → dwd → dwm → dws → ads 理解链路走向；dim 为维表。
- 链路上有 SLA 或基线任务的表必须在报告中明确点出——它们是变更风险最高的下游。

## 分析套路

- "改 X 表的 Y 字段影响哪些下游"：优先 `impact_analysis`（字段级）。
  若结果带 `degraded: true`，说明没有字段级血缘、已降级为表级下游分析，
  必须在结论中如实说明这一点，不得假装是精确的字段级结果。
- "这个表的上下游"：`get_full_chain`；只关心一个方向时用
  `get_upstream` / `get_downstream`。
- "A 表和 B 表是怎么连起来的"：`find_path`（自动双向尝试最短路径）。
- "X 表延迟了 N 小时会影响哪些 SLA/基线"：`sla_impact`（传 delay_hours），
  结果按跳数和 SLA 产出时间排序，越近越早的越危险。
- "帮我体检一下血缘/找环依赖/哪些表可以下线"：`health_check`（全图分析：
  环依赖 / 孤立表 / 无下游可下线表）。
- 表名不确定：先 `search_tables`，向用户列出候选后再查询。
- 查询返回 `error` + `suggestions` 时，从 suggestions 中挑最接近的表重试，
  或在结论中告知未找到。
- 链路过大（`truncated: true`）：在结论里提示用户收窄方向或减小深度。

## 提交要求

- 必须先至少调用一次血缘查询工具，再调用 **submit_lineage_report**
  （summary 用中文，涵盖影响范围 + SLA/基线风险提示）。
- submit 返回的 report 必须**原样**作为最终答案输出，前后不加任何内容。
