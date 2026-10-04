-- Schema 漂移演示 · 新版本快照
-- 对比旧版本：phone 列被删除（破坏）、age INT→BIGINT（风险，拓宽）、
-- amount DECIMAL(10,2)→DECIMAL(16,2)（风险）、新增 email 列（提示）、
-- user_name 注释变更（提示）、order_detail 分区从 dt 变为 dt+hour（破坏）、
-- tmp.legacy_report 被删除（破坏）、新增 ads.user_summary（提示）
CREATE TABLE ods.user_info (
  user_id   BIGINT COMMENT '用户ID',
  user_name STRING COMMENT '用户真实姓名',
  age       BIGINT COMMENT '年龄',
  amount    DECIMAL(16,2) COMMENT '累计消费',
  email     STRING COMMENT '电子邮箱'
) COMMENT '用户基础信息表'
PARTITIONED BY (dt STRING COMMENT '分区日期')
STORED AS ORC;

CREATE TABLE ods.order_detail (
  order_id  BIGINT COMMENT '订单ID',
  user_id   BIGINT COMMENT '用户ID',
  sku_cnt   INT COMMENT '商品数量'
) COMMENT '订单明细'
PARTITIONED BY (dt STRING, hour STRING)
STORED AS ORC;

CREATE TABLE ads.user_summary (
  user_id   BIGINT COMMENT '用户ID',
  pay_cnt   BIGINT COMMENT '支付次数'
) PARTITIONED BY (dt STRING)
STORED AS ORC;
