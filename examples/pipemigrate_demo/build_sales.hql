-- daily sales wide table
INSERT OVERWRITE TABLE dws.sales PARTITION (dt = '${hiveconf:dt}')
SELECT o.order_id, o.amount, u.region
FROM ods.orders o
JOIN ods.users u ON o.user_id = u.user_id
WHERE o.dt = '${hiveconf:dt}';

INSERT OVERWRITE TABLE ads.sales_report PARTITION (dt = '${hiveconf:dt}')
SELECT region, SUM(amount) FROM dws.sales
WHERE dt = '${hiveconf:dt}' GROUP BY region;
