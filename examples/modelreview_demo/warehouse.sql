-- 建模体检演示：故意埋了几类结构问题
CREATE TABLE dim.users (
  user_name  STRING COMMENT '用户姓名',
  city       STRING COMMENT '城市',
  reg_date   DATE COMMENT '注册日期'
) COMMENT '用户维表（缺主键列 → MR001）'
STORED AS ORC;

CREATE TABLE dwd.orders (
  order_id    BIGINT COMMENT '订单ID',
  user_id     BIGINT COMMENT '用户ID',
  user_name   STRING COMMENT '用户姓名（混入事实表 → MR003/MR004）',
  amount      DECIMAL(16,2) COMMENT '金额'
) COMMENT '订单事实表（未分区 → MR002）'
STORED AS ORC;

CREATE TABLE dwd.payments (
  pay_id      BIGINT COMMENT '支付ID',
  order_id    BIGINT COMMENT '订单ID',
  user_name   STRING COMMENT '用户姓名（与 dwd.orders 复制 → MR004）',
  pay_amount  DECIMAL(16,2) COMMENT '支付金额'
) PARTITIONED BY (dt STRING)
STORED AS ORC;

CREATE TABLE dws.user_profile_tags (
  user_id   BIGINT COMMENT '用户ID',
  tag_a     STRING COMMENT '标签A',
  tag_b     STRING COMMENT '标签B'
) COMMENT '汇总表（无度量列 → MR005）'
PARTITIONED BY (dt STRING)
STORED AS ORC;
