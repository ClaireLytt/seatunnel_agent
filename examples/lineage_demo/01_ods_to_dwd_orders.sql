-- ODS -> DWD: 订单明细清洗
INSERT OVERWRITE TABLE dwd.orders_di
SELECT
    o.order_id,
    o.user_id,
    o.amount,
    o.create_time,
    u.city
FROM ods.orders_raw o
LEFT JOIN ods.users_raw u ON o.user_id = u.user_id
WHERE o.amount > 0;
