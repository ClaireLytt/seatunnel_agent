-- Data Skew demo script (used by the DSK18 UI test case and handy for
-- trying the /dataskew page or `seatunnel-agent skew -f examples/skew_demo.sql`).
-- Deliberately trips three static rules:
--   DS001: COUNT(DISTINCT) single-point aggregation
--   DS007: LEFT JOIN key without a NULL filter
--   DS005: trailing global ORDER BY without LIMIT
SELECT o.category,
       count(distinct o.user_id) AS uv
FROM ods.orders o
LEFT JOIN ods.users u ON o.user_id = u.id
GROUP BY o.category
ORDER BY uv;
