-- skew-prone join: hot key + no salt, for the skew_check demo
SELECT a.user_id, COUNT(1) AS pv, SUM(b.amount) AS gmv
FROM dwd_click_di a
JOIN dwd_order_df b ON a.user_id = b.user_id
WHERE a.ds = '2026-10-01' AND b.ds = '2026-10-01'
GROUP BY a.user_id;
