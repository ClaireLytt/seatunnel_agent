# Text2SQL 意图规则（Intent Rules）

## 表/字段匹配
- 对用户问题分词，统计与每张表 comment、字段 comment 命中的关键词数量，取 top-N 候选表；同分时优先字段级匹配更多的表。
- 字段匹配优先级：**英文列名优先，中文 comment 兜底**（coalesce(英文, 中文) 思路）。
- 用户用中文描述字段时（中文指 column 的 comment），通过 comment 反查列名。

## WHERE 条件与时间范围
- 用户提到时间词（"最近30天"、"3月13日"、"2026-03-13" 等）→ 转换成对应时间字段（优先英文时间字段）的 `>=` / `BETWEEN` 条件。
- 对用户询问的字段信息（优先取英文）进行 WHERE 筛选。

## 分区筛选（必须遵守，防止全表扫描）
| 表后缀 | 含义 | 分区策略 |
|---|---|---|
| `_di` | 日增量表 | 有时间范围 → 按时间换算 pt；无 → 取最大分区 |
| `_hi` | 小时增量表 | 同上 |
| `_ri` | 实时增量表 | 同上 |
| `_df` | 日全量表 | 优先匹配用户描述的 T+1 分区；无 → 取最大分区 |
| `_hf` | 小时全量表 | 同上 |
| 无后缀 | 普通表 | 一律取最大分区兜底 |

- 增量表示例：`where pt='20260313' and inbound_create_time>='2026-03-13 00:00:00'`
- 全量表/无时间描述：`where pt='<最大分区>'`（先调用 get_max_partition 获取）。

## 字段范围
- 用户明确指定字段 → 优先按英文列名映射，找不到再按中文 comment 反查。
- 用户未指定字段 → `SELECT *`（仍必须带分区裁剪）。

## 结果中文化展示
- 每个 SELECT 字段自动加中文别名（取字段 comment），如：
  ```sql
  select date_id as 日期, level1_category_name as 商品一级类目
  ```
- 无 comment 的字段保留原始列名。

## 多表关联
- 优先找两表的**同名字段**作为 JOIN key；找不到时按 comment 语义最接近的字段关联。
- 用户"两边都要" → `JOIN`；"只要一边的信息" → `LEFT JOIN`。
- 分区表 JOIN 前先做谓词下推（子查询里各自过滤分区/条件，再 JOIN）。

## 聚合
- 识别"合计/总量/多少笔/count/sum"等词 → 生成聚合列并自动补 `GROUP BY` 维度字段。
  ```sql
  select warhouse_name as 仓库名, count(inbound_id) as 最近30天的入库单量
  from zz.dwm_scm_detail_di
  where pt >= '20260213'
  group by warhouse_name
  ```

## 开窗
- 识别"第一个/最早/最新/前N个"等语义 → `ROW_NUMBER() OVER(...)` / `LEAD()`，外层 `WHERE rn = 1` 收口。
  ```sql
  select spu from (
    select spu_id as spu,
           row_number() over(order by inbound_create_time asc) as rn
    from zz.dwm_scm_detail_di
    where pt = '20260313'
  ) t where rn = 1
  ```

## 执行与导出
- 执行前：打印最终 SQL。
- 执行后：打印执行日志（耗时、返回行数）、结果预览（默认前20行）。
- 导出：默认写到本机 Desktop 目录，文件名带时间戳；用户指定路径则按指定路径写 CSV。
