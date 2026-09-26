INSERT OVERWRITE TABLE dws.user_stats PARTITION (dt = '${bizdate}')
SELECT
  user_id,
  SUM(amount) AS total_amount,
  COUNT(1) AS order_cnt
FROM dwd.orders_di
WHERE dt = '${bizdate}'
GROUP BY user_id;
