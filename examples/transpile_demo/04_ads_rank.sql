-- Window function + date functions: fully automatic translation
SELECT
  dt,
  user_id,
  gmv,
  ROW_NUMBER() OVER (PARTITION BY dt ORDER BY gmv DESC) AS rn,
  date_add(dt, 1) AS next_dt
FROM dws.gmv_daily
WHERE dt = '${bizdate}';
