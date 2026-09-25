-- JSON extraction + partition write: translates automatically, with notes
INSERT OVERWRITE TABLE dwd.orders_di PARTITION (dt = '${bizdate}')
SELECT
  order_id,
  user_id,
  amount,
  get_json_object(payload, '$.channel') AS channel
FROM ods.orders_raw
WHERE dt = '${bizdate}'
  AND amount > 0;
