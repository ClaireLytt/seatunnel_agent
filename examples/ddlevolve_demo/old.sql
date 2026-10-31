-- Schema 漂移演示 · 旧版本快照
CREATE TABLE ods.user_info (
  user_id   BIGINT COMMENT '用户ID',
  user_name STRING COMMENT '用户姓名',
  phone     STRING COMMENT '手机号',
  age       INT COMMENT '年龄',
  amount    DECIMAL(10,2) COMMENT '累计消费'
) COMMENT '用户基础信息表'
PARTITIONED BY (dt STRING COMMENT '分区日期')
STORED AS ORC;

CREATE TABLE ods.order_detail (
  order_id  BIGINT COMMENT '订单ID',
  user_id   BIGINT COMMENT '用户ID',
  sku_cnt   INT COMMENT '商品数量'
) COMMENT '订单明细'
PARTITIONED BY (dt STRING)
STORED AS ORC;

CREATE TABLE tmp.legacy_report (
  report_id BIGINT,
  content   STRING
) STORED AS ORC;
