CREATE TABLE ods.orders (
  order_id BIGINT,
  user_id BIGINT,
  amount DOUBLE,
  status STRING,
  dt STRING
) PARTITIONED BY (status) STORED AS PARQUET;

CREATE TABLE ods.users (
  user_id BIGINT,
  region STRING,
  updated_at TIMESTAMP
) CLUSTERED BY (updated_at) INTO 16 BUCKETS STORED AS PARQUET;
