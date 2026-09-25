-- Clean aggregation: fully automatic translation
SELECT
  dt,
  channel,
  SUM(amount) AS gmv,
  COUNT(DISTINCT user_id) AS buyers
FROM dwd.orders_di
WHERE dt BETWEEN '${startdate}' AND '${enddate}'
GROUP BY dt, channel;
