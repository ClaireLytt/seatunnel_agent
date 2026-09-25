INSERT OVERWRITE TABLE dws.gmv_daily PARTITION (dt = '${bizdate}')
SELECT
  dt,
  channel,
  SUM(amount) AS gmv,
  COUNT(DISTINCT user_id) AS buyers
FROM dwd.orders_di
WHERE dt = '${bizdate}'
GROUP BY dt, channel;
