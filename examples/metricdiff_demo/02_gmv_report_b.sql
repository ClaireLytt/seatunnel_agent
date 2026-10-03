-- 口径一致性演示 · 报表 B：gmv = sum(amount - refund)（净口径）→ 与报表 A 冲突
-- order_cnt 用 count(*)，与报表 A 的 count(1) 归一化后等价 → 不报冲突
INSERT OVERWRITE TABLE ads.gmv_report_b
SELECT
  o.user_id,
  sum(o.amount - o.refund) AS gmv,
  count(*)                 AS order_cnt,
  o.dt
FROM dwd.orders o
GROUP BY o.user_id, o.dt;
