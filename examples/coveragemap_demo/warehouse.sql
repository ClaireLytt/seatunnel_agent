CREATE TABLE dwd.orders (
  order_id BIGINT COMMENT '订单ID',
  user_id  BIGINT COMMENT '用户ID',
  amount   DECIMAL(16,2) COMMENT '金额'
) PARTITIONED BY (dt STRING) STORED AS ORC;

CREATE TABLE dws.orders_daily (
  order_date STRING COMMENT '日期',
  gmv        DECIMAL(18,2) COMMENT 'GMV'
) PARTITIONED BY (dt STRING) STORED AS ORC;

CREATE TABLE dim.users (
  user_id   BIGINT COMMENT '用户ID',
  user_name STRING COMMENT '姓名'
) STORED AS ORC;

CREATE TABLE tmp.scratch (
  x INT COMMENT '草稿'
) STORED AS ORC;
