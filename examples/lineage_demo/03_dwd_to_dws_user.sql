-- DWD -> DWS: 用户消费画像
INSERT OVERWRITE TABLE dws.user_stats
SELECT
    user_id,
    count(*) AS order_cnt,
    sum(amount) AS total_amount,
    max(create_time) AS last_order_time
FROM dwd.orders_di
GROUP BY user_id;
