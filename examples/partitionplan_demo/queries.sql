SELECT SUM(amount) FROM dwd.orders WHERE order_date = '2026-10-30';

SELECT COUNT(*) FROM dwd.orders
WHERE order_date >= '2026-10-01' AND status = 'paid';

SELECT * FROM dwd.orders WHERE user_id = 42;

SELECT amount FROM dwd.orders WHERE order_id = 10042;

SELECT status, COUNT(*) FROM dwd.orders GROUP BY status;
