INSERT OVERWRITE TABLE dwd.orders_di PARTITION (dt = '${bizdate}')
SELECT
  order_id,
  user_id,
  amount,
  refund_amount,
  channel
FROM ods.orders_raw
WHERE dt = '${bizdate}';
