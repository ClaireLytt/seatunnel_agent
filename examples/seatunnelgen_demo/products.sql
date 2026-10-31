CREATE TABLE inventory.products (
  product_id BIGINT COMMENT '商品ID',
  name       STRING COMMENT '商品名称',
  price      DECIMAL(10,2) COMMENT '价格',
  updated_at TIMESTAMP COMMENT '更新时间'
) COMMENT '商品表'
STORED AS ORC;
