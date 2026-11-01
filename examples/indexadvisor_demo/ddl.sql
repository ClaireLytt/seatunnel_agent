CREATE TABLE ods.orders (
  order_id BIGINT,
  user_id BIGINT,
  amount DOUBLE,
  status STRING,
  dt STRING
) STORED AS PARQUET;

CREATE TABLE ods.users (
  user_id BIGINT,
  region STRING,
  updated_at TIMESTAMP
) STORED AS PARQUET;
