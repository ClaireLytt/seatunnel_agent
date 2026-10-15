# SQL Code Review 检查清单

对提交的 SQL 逐项检查以下 5 大类 15 个检查项。每一项都要给出结论：
通过 / 问题（严重，必须修复）/ 风险（建议修复）/ 建议（可选优化）。

## 一、语法正确性

1. **JOIN 关联条件与字段准确性** (join_condition)
   - 关联条件是否正确、关联字段是否准确
   - 两侧字段类型是否一致（string vs bigint 隐式转换会导致关联失效或全表扫描）
2. **JOIN 类型与笛卡尔积** (join_cartesian)
   - 是否存在多对多关联放大、缺少 ON 条件的笛卡尔积
   - LEFT/RIGHT/INNER 选择是否符合业务语义
3. **WHERE 条件语法与 NULL 判断** (where_syntax)
   - 条件书写语法是否正确
   - NULL 判断必须使用 IS NULL / IS NOT NULL，不能用 = / !=
   - LEFT JOIN 后在 WHERE 中过滤右表字段会退化为 INNER JOIN
4. **时间范围与分区条件书写** (where_partition)
   - 时间范围筛选边界是否正确（>= 与 <、闭开区间）
   - 分区书写是否正确（分区值类型、格式、变量引用如 ${bizdate}）
5. **GROUP BY 字段完整性** (groupby_completeness)
   - SELECT 中所有非聚合字段必须出现在 GROUP BY 中
   - 聚合函数名是否正确
6. **聚合函数使用正确性** (aggregate_functions)
   - COUNT(1)/COUNT(*)/COUNT(col) 语义区别（COUNT(col) 不计 NULL）
   - SUM/AVG 对 NULL 的处理是否符合预期
7. **计算逻辑** (calculation)
   - 算术运算是否考虑 NULL 和除零（NULLIF/COALESCE 保护）
   - 金额计算精度是否正确（分/元转换、DECIMAL vs DOUBLE 浮点误差）
   - 比例/百分比计算逻辑（分母口径、乘 100 时机、整数除法截断）

## 二、数据质量

8. **空值处理** (null_handling)
   - 关键字段是否有 NULL 检查
   - COALESCE/NVL 使用是否正确
   - 空字符串 '' 与 NULL 是否区分处理
9. **去重逻辑** (dedup)
   - 是否存在重复数据风险（JOIN 放大、UNION ALL 重复）
   - 去重逻辑是否正确（ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...) = 1 vs GROUP BY vs DISTINCT）
   - 主键/去重键是否唯一
10. **数据类型** (type_cast)
    - 类型转换是否正确（CAST 显式转换优于隐式）
    - 字符串与数值比较是否合理
    - 时间类型格式是否统一（yyyyMMdd vs yyyy-MM-dd）

## 三、SQL 性能

11. **分区裁剪** (partition_pruning)
    - 是否进行分区过滤（pt/dt/ds 等分区列）
    - 分区列上不要套函数，否则裁剪失效
    - 动态分区是否合理、二级分区粒度是否合适
12. **数据倾斜** (data_skew)
    - 是否存在热点 Key（NULL 值、默认值集中）
    - 大表 JOIN 是否优化（MAPJOIN 小表广播、倾斜键打散）
    - GROUP BY / COUNT(DISTINCT) 是否需要两阶段分散
13. **资源使用** (resource_usage)
    - 是否有不必要的大表扫描（SELECT *、缺少列裁剪）
    - 重复引用的复杂子查询是否应固化为中间临时表
    - 是否可以增量处理替代全量重算
    - ORDER BY 全局排序是否必要

## 四、代码规范

14. **可读性** (readability)
    - 复杂逻辑是否有注释说明
    - SQL 格式是否规范（缩进、关键字大小写一致、别名有意义）

## 五、逻辑问题

15. **时间边界** (time_boundary)
    - 跨天/跨月统计边界是否正确（月末、年末、闰年 2 月 29）
    - 时区问题（UTC vs 本地时间、unix_timestamp 转换）
    - 时间比较的开闭区间（BETWEEN 是闭区间）

## 方言注意事项

- **Hive SQL**：ORDER BY 全局单 reducer；分区列过滤必须；`!=` 对 NULL 无效；
  整数相除结果为 double（Hive 2+）。
- **Spark SQL**：与 Hive 大体一致；注意 `spark.sql.shuffle.partitions`；
  ANSI 模式下除零报错，非 ANSI 返回 NULL。
- **Flink SQL**：流式语义 — 检查窗口（TUMBLE/HOP/CUMULATE）定义、事件时间与
  watermark、状态 TTL；不适用分区裁剪/ORDER BY 无 LIMIT 规则；
  流上的 JOIN 需关注状态无限增长。
- **MaxCompute SQL**：分区过滤是强制最佳实践；分区值必须为字符串常量比较；
  不支持部分 Hive UDF；INSERT OVERWRITE 必须带分区。
