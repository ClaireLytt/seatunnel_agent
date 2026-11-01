CREATE TABLE orders (
  order_id BIGINT NOT NULL,
  user_id BIGINT,
  amount DECIMAL(38,6),
  note VARCHAR(256),
  created_at TIMESTAMP,
  channel VARCHAR(32)
);
