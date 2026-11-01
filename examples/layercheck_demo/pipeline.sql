-- demo pipeline with layering violations
INSERT INTO dwd.orders
SELECT order_id, user_id, amount, order_date FROM ods.orders_raw;

INSERT INTO dws.orders_daily
SELECT o.order_date, SUM(o.amount) AS gmv
FROM dwd.orders o JOIN dim.users u ON o.user_id = u.user_id
GROUP BY o.order_date;

-- violation: ads reads ods directly (skips dwd and dws)
INSERT INTO ads.board_kpi
SELECT order_date, COUNT(*) FROM ods.orders_raw GROUP BY order_date;

-- violation: dwd reads dws (reverse dependency)
INSERT INTO dwd.orders_enriched
SELECT * FROM dws.orders_daily;

-- smell: ads stacked on ads
INSERT INTO ads.board_v2
SELECT * FROM ads.board_kpi;
