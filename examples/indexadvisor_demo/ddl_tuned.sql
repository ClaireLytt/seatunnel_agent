CREATE TABLE ods.orders (
  order_id BIGINT,
  user_id BIGINT,
  amount DOUBLE,
  status STRING,
  dt STRING
) PARTITIONED BY (dt) CLUSTERED BY (user_id) INTO 32 BUCKETS
  STORED AS PARQUET;

CREATE TABLE ods.users (
  user_id BIGINT,
  region STRING,
  updated_at TIMESTAMP
) CLUSTERED BY (region) INTO 32 BUCKETS STORED AS PARQUET;

CREATE TABLE dim.regions (
  region STRING,
  region_name STRING
) CLUSTERED BY (region) INTO 8 BUCKETS STORED AS PARQUET;
