CREATE TABLE ods_orders (
  order_id INT NOT NULL,
  amount DECIMAL(18,2),
  note VARCHAR(64),
  created_at DATE,
  channel VARCHAR(64) NOT NULL,
  etl_time TIMESTAMP NOT NULL
);
