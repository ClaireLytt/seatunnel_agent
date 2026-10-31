-- 新版：改口径 + 收紧过滤 + 去掉维表 join
INSERT OVERWRITE TABLE dws.orders_daily
SELECT o.order_date,
       o.user_id,
       SUM(o.pay_amount) AS gmv
FROM dwd.orders o
WHERE o.order_date >= '2026-01-01'
  AND o.status = 'PAID'
GROUP BY o.order_date, o.user_id;
