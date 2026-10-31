-- demo pipeline: ods -> dwd -> dws
INSERT INTO dwd.orders
SELECT order_id, user_id, CAST(amount AS DOUBLE) AS amount, order_date
FROM ods.orders_raw;

INSERT INTO dws.orders_daily
SELECT o.order_date, o.user_id, SUM(o.amount) AS gmv
FROM dwd.orders o
JOIN dim.users u ON o.user_id = u.user_id
GROUP BY o.order_date, o.user_id;
