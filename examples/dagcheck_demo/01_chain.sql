-- DAG 体检演示 · 正常三级链路 ods → dwd → dws → ads
INSERT OVERWRITE TABLE dwd.orders
SELECT order_id, user_id, amount, dt FROM ods.orders WHERE dt = '2024-01-01';

INSERT OVERWRITE TABLE dws.gmv
SELECT user_id, sum(amount) AS gmv, dt FROM dwd.orders GROUP BY user_id, dt;

INSERT OVERWRITE TABLE ads.gmv_report
SELECT user_id, gmv, dt FROM dws.gmv;
