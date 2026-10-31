-- 旧版：订单日汇总
INSERT INTO dws.orders_daily
SELECT o.order_date,
       o.user_id,
       SUM(o.amount) AS gmv,
       COUNT(*) AS order_cnt
FROM dwd.orders o
JOIN dim.users u ON o.user_id = u.user_id
WHERE o.order_date >= '2026-01-01'
GROUP BY o.order_date, o.user_id;
