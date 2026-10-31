SELECT u.region, SUM(o.amount)
FROM ods.orders o
JOIN ods.users u ON o.user_id = u.user_id
WHERE substr(o.dt, 1, 10) = '2024-05-01'
GROUP BY u.region;
