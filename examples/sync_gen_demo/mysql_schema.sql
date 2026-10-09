-- 全库同步生成器 demo：模拟一个业务库 shop 的 MySQL DDL 快照
-- 覆盖类型矩阵 + PII 列 + 过滤演示表（*_tmp / *_bak）

CREATE TABLE shop.users (
  id BIGINT UNSIGNED NOT NULL,
  user_name VARCHAR(64) COMMENT '用户昵称',
  phone VARCHAR(20) COMMENT '手机号',
  email VARCHAR(128) COMMENT '电子邮件地址',
  id_card CHAR(18) COMMENT '身份证号码',
  gender TINYINT(1) COMMENT '性别 0女1男',
  birthday DATE COMMENT '出生日期',
  created_at DATETIME NOT NULL COMMENT '注册时间',
  PRIMARY KEY (id)
) COMMENT='用户表';

CREATE TABLE shop.orders (
  order_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL COMMENT '下单用户',
  amount DECIMAL(12,2) NOT NULL COMMENT '订单金额',
  status ENUM('pending','paid','shipped','done','cancelled') COMMENT '订单状态',
  pay_time DATETIME(3) COMMENT '支付时间',
  remark TEXT COMMENT '订单备注',
  PRIMARY KEY (order_id)
) COMMENT='订单表';

CREATE TABLE shop.products (
  sku_id INT UNSIGNED NOT NULL,
  sku_name VARCHAR(255) COMMENT '商品名称',
  price DECIMAL(10,2) COMMENT '售价',
  stock MEDIUMINT COMMENT '库存',
  attrs JSON COMMENT '扩展属性',
  detail LONGTEXT COMMENT '商品详情',
  on_sale BIT(1) COMMENT '是否在售',
  PRIMARY KEY (sku_id)
) COMMENT='商品表';

-- 无主键 + weak PII 命中（name 列）演示
CREATE TABLE shop.user_address (
  user_id BIGINT NOT NULL,
  name VARCHAR(32) COMMENT '收件人',
  address VARCHAR(512) COMMENT '收货地址',
  geo GEOMETRY COMMENT '坐标',
  updated_at TIMESTAMP COMMENT '更新时间'
) COMMENT='收货地址表';

-- 以下两张表用于演示 --exclude '.*_(tmp|bak)$'
CREATE TABLE shop.order_items_tmp (
  id BIGINT NOT NULL,
  order_id BIGINT,
  PRIMARY KEY (id)
) COMMENT='临时表';

CREATE TABLE shop.users_bak (
  id BIGINT NOT NULL,
  phone VARCHAR(20) COMMENT '手机号',
  PRIMARY KEY (id)
) COMMENT='备份表';
