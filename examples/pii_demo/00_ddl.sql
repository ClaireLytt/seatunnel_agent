-- PII 扫描演示：建表语句（列名 + 中文注释是规则匹配的两个来源）
CREATE TABLE IF NOT EXISTS ods.user_info (
  user_id     BIGINT COMMENT '用户ID',
  user_name   STRING COMMENT '用户姓名',
  phone       STRING COMMENT '手机号',
  id_card_no  STRING COMMENT '身份证号',
  email       STRING COMMENT '电子邮箱',
  home_addr   STRING COMMENT '家庭住址',
  reg_time    STRING COMMENT '注册时间'
) COMMENT '用户基础信息表'
PARTITIONED BY (dt STRING COMMENT '分区日期')
STORED AS ORC;

CREATE TABLE IF NOT EXISTS ods.order_pay (
  order_id    BIGINT COMMENT '订单ID',
  user_id     BIGINT COMMENT '用户ID',
  bank_card_no STRING COMMENT '付款银行卡号',
  amount      DOUBLE COMMENT '支付金额',
  lianxi      STRING COMMENT '收件人联系方式'
) COMMENT '订单支付表'
PARTITIONED BY (dt STRING)
STORED AS ORC;
