-- 测试数据生成演示：两表关联 + 分区过滤 + IN 条件
SELECT u.user_id, u.user_name, sum(o.amount) AS pay_amount
FROM dwd.user_info u
JOIN dwd.order_pay o ON u.user_id = o.user_id
WHERE o.dt = '2024-01-01' AND o.status IN ('PAID', 'DONE')
GROUP BY u.user_id, u.user_name
