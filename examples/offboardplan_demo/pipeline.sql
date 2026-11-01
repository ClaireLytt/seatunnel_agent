-- 调度文件生成演示：三层链路 + 脚本外上游
INSERT INTO dws.orders_daily
SELECT o.order_date, o.user_id, SUM(o.amount) AS gmv
FROM dwd.orders o
JOIN dim.users u ON o.user_id = u.user_id
GROUP BY o.order_date, o.user_id;

INSERT INTO ads.order_counts
SELECT order_date, COUNT(*) AS order_cnt
FROM dwd.orders
GROUP BY order_date;

INSERT INTO ads.final_report
SELECT a.order_date, a.gmv, b.order_cnt
FROM dws.orders_daily a
JOIN ads.order_counts b ON a.order_date = b.order_date;
