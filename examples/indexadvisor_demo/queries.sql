-- daily revenue by region
SELECT u.region, SUM(o.amount)
FROM ods.orders o
JOIN ods.users u ON o.user_id = u.user_id
WHERE o.dt = '2024-05-01' AND o.status = 'PAID'
GROUP BY u.region;

-- user order history lookup
SELECT o.order_id, o.amount
FROM ods.orders o
WHERE o.dt = '2024-05-01' AND o.user_id = 42 AND o.amount > 100;

-- weekly paid orders per user
SELECT o.user_id, COUNT(*)
FROM ods.orders o
WHERE o.dt BETWEEN '2024-04-25' AND '2024-05-01' AND o.status = 'PAID'
GROUP BY o.user_id;

-- region dimension refresh join
SELECT u.user_id, u.region
FROM ods.users u
JOIN dim.regions r ON u.region = r.region
WHERE u.updated_at > '2024-05-01';
