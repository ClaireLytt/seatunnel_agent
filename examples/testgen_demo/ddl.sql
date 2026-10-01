-- 可选 DDL：提供精确列类型（不提供时按用法推断）
CREATE TABLE dwd.user_info (
  user_id   BIGINT COMMENT '用户ID',
  user_name STRING COMMENT '用户姓名'
) PARTITIONED BY (dt STRING COMMENT '分区日期')
STORED AS ORC;

CREATE TABLE dwd.order_pay (
  order_id  BIGINT COMMENT '订单ID',
  user_id   BIGINT COMMENT '用户ID',
  amount    DECIMAL(16,2) COMMENT '支付金额',
  status    STRING COMMENT '订单状态'
) PARTITIONED BY (dt STRING)
STORED AS ORC;
