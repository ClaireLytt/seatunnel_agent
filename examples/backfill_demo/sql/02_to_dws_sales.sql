-- DWD + ODS -> DWS: 销售汇总
INSERT OVERWRITE TABLE dws.sales
SELECT o.order_id, o.amount, i.item_name
FROM dwd.orders o
JOIN ods.items i ON o.order_id = i.order_id;
