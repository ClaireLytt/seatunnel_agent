CREATE TABLE dwd.orders (
  order_id    BIGINT COMMENT '订单ID',
  user_id     BIGINT COMMENT '用户ID',
  amount      DECIMAL(16,2) COMMENT '金额',
  note        STRING COMMENT '备注',
  legacy_flag INT COMMENT '历史标记'
) STORED AS ORC;

CREATE TABLE dim.users (
  user_id   BIGINT COMMENT '用户ID',
  user_name STRING COMMENT '姓名',
  city      STRING COMMENT '城市'
) STORED AS ORC;

CREATE TABLE tmp.old_backup (
  x INT COMMENT '废弃'
) STORED AS ORC;
