-- CHANGED: no longer joins dws.user_stats — an upstream was dropped
INSERT OVERWRITE TABLE ads.gmv_report PARTITION (dt = '${bizdate}')
SELECT
  g.dt,
  g.channel,
  g.gmv,
  g.buyers
FROM dws.gmv_daily g
WHERE g.dt = '${bizdate}';
