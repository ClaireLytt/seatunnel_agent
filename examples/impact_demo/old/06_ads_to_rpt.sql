INSERT OVERWRITE TABLE rpt.gmv_dashboard PARTITION (dt = '${bizdate}')
SELECT
  dt,
  channel,
  gmv
FROM ads.gmv_report
WHERE dt = '${bizdate}';
