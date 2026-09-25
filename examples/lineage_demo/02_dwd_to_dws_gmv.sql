-- DWD -> DWS: 每日 GMV 汇总
INSERT OVERWRITE TABLE dws.gmv_daily
SELECT
    to_date(create_time) AS stat_date,
    city,
    sum(amount) AS gmv,
    count(DISTINCT user_id) AS buyer_cnt
FROM dwd.orders_di
GROUP BY to_date(create_time), city;
