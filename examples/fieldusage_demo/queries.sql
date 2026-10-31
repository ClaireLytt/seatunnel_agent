SELECT o.order_id, o.amount FROM dwd.orders o WHERE o.user_id = 1;

SELECT u.user_name, SUM(o.amount) AS gmv
FROM dwd.orders o
JOIN dim.users u ON o.user_id = u.user_id
GROUP BY u.user_name;

SELECT * FROM dwd.orders;

SELECT amount FROM dwd.orders;
