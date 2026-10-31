-- 重复建设演示：两个团队从同样的源各建了一张日汇总
INSERT INTO dws.orders_daily
SELECT o.order_date, o.user_id, SUM(o.amount) AS gmv
FROM dwd.orders o
JOIN dim.users u ON o.user_id = u.user_id
GROUP BY o.order_date, o.user_id;

INSERT INTO dws.order_summary_bi
SELECT o.order_date, o.user_id, SUM(o.amount) AS gmv
FROM dwd.orders o
JOIN dim.users u ON o.user_id = u.user_id
GROUP BY o.order_date, o.user_id;

-- 子集派生候选：只读 dwd.orders 一张
INSERT INTO ads.order_counts
SELECT order_date, COUNT(*) AS order_cnt
FROM dwd.orders
GROUP BY order_date;

-- 高扇出：dwd.orders 被 4 个目标直读
INSERT INTO ads.user_gmv_rank
SELECT user_id, SUM(amount) AS total_gmv
FROM dwd.orders
GROUP BY user_id;
