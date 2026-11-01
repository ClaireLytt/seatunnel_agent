SELECT user_id, SUM(gmv) FROM dws.orders_daily WHERE order_date >= date_sub(current_date, 7) GROUP BY user_id;
SELECT o.order_id, u.city FROM dwd.orders o JOIN dim.users u ON o.user_id = u.user_id WHERE o.channel = "app";
