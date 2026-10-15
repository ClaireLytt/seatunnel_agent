# Spark/Hive SQL 性能优化规则

核心目标：在确保最终输出结果与原始 SQL 完全一致的前提下优化执行性能。

## 1. 谓词下推：过滤条件尽早执行
```sql
-- ✅ 先过滤再 JOIN
SELECT a.*, b.*
FROM (SELECT * FROM user_events WHERE dt = '2026-03-12') a
JOIN user_profiles b ON a.user_id = b.user_id;
```

## 2. 避免重复子查询：优先用 CTE 复用
```sql
WITH base AS (SELECT * FROM user_events WHERE dt = '2026-03-12')
SELECT * FROM base WHERE event = 'click'
UNION ALL
SELECT * FROM base WHERE event = 'buy';
```

## 3. 分区剪枝：不要对分区字段做函数转换
```sql
-- ❌ DATE_FORMAT(dt,'yyyy-MM') = '2026-03' 会让分区剪枝失效
-- ✅ dt >= '2026-03-01' AND dt < '2026-04-01'
```

## 4. 广播小表（MAPJOIN）
维度表/字典表行数 < 100 万或体积 < 50MB 时：
```sql
SELECT /*+ MAPJOIN(dim) */ a.user_id, b.category
FROM user_events a JOIN dim_category b ON a.category_id = b.category_id;
```

## 5. 避免笛卡尔积和隐式 JOIN
必须写全 ON 条件，禁止 `FROM a, b` 无关联条件写法。

## 6. Group By 数据倾斜：三步加盐聚合
适用：SUM / COUNT(*) / MAX / MIN（AVG 需改写为 SUM/COUNT）。
**不适用于 COUNT(DISTINCT ...)**（打散后会重复计数）。
```sql
WITH salted AS (
  SELECT user_id, amount, CAST(FLOOR(RAND() * 40) AS INT) AS salt
  FROM orders WHERE status = 'paid'
),
stage1 AS (
  SELECT user_id, salt, COUNT(*) AS partial_cnt, SUM(amount) AS partial_sum
  FROM salted GROUP BY user_id, salt
)
SELECT user_id, SUM(partial_cnt) AS order_cnt, SUM(partial_sum) AS total_amount
FROM stage1 GROUP BY user_id;
```
注意：salt 必须在 CTE 中固化一次，不要在同一层 SELECT 和 GROUP BY 中写两次 RAND()。
盐值从 8/16/32 起步，按倾斜程度调整。
