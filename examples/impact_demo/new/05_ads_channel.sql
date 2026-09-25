-- NEW FILE: a brand-new downstream report (info-level addition)
INSERT OVERWRITE TABLE ads.channel_report PARTITION (dt = '${bizdate}')
SELECT
  dt,
  channel,
  gmv
FROM dws.gmv_daily
WHERE dt = '${bizdate}';
