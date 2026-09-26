INSERT OVERWRITE TABLE ads.gmv_report PARTITION (dt = '${bizdate}')
SELECT
  g.dt,
  g.channel,
  g.gmv,
  g.buyers,
  u.total_amount
FROM dws.gmv_daily g
LEFT JOIN dws.user_stats u ON g.dt = u.dt
WHERE g.dt = '${bizdate}';
