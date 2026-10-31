SELECT u.region, SUM(o.amount)
FROM ods.orders o
JOIN ods.users u ON o.user_id = u.user_id
WHERE o.dt = '2024-05-01'
GROUP BY u.region;
