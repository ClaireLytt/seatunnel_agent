-- Hive DDL: storage clauses must be rewritten for Doris/StarRocks
CREATE TABLE ods.orders_raw (
  order_id BIGINT,
  user_id BIGINT,
  amount DECIMAL(16, 2),
  payload STRING,
  dt STRING
)
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY');
