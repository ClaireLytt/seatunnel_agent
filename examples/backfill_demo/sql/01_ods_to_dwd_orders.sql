-- ODS -> DWD: 订单明细
INSERT OVERWRITE TABLE dwd.orders
SELECT o.order_id, o.user_id, o.amount, u.city
FROM ods.orders o
LEFT JOIN ods.users u ON o.user_id = u.user_id;
