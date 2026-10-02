-- 口径一致性演示 · 报表 A：gmv = sum(amount)（毛口径）
INSERT OVERWRITE TABLE ads.gmv_report_a
SELECT
  o.user_id,
  sum(o.amount)   AS gmv,
  count(1)        AS order_cnt,
  o.dt
FROM dwd.orders o
GROUP BY o.user_id, o.dt;
