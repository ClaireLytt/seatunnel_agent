-- Governance demo warehouse: every governance agent finds something here.
-- ods: raw landing
CREATE TABLE ods.raw_events (
  event_id BIGINT COMMENT 'event id',
  user_phone STRING COMMENT '用户手机号',
  amount DOUBLE,
  birth_date STRING COMMENT 'birth date as text',
  line STRING
) PARTITIONED BY (dt STRING COMMENT 'partition day');

-- dwd fact: unowned, money on DOUBLE, PII spreads here
CREATE TABLE dwd.fact_orders (
  order_id BIGINT COMMENT 'order id',
  user_phone STRING COMMENT '用户手机号',
  pay_amount DOUBLE COMMENT 'paid amount',
  memo STRING COMMENT 'note'
) PARTITIONED BY (dt STRING COMMENT 'partition day');

INSERT INTO dwd.fact_orders
SELECT event_id, user_phone, amount, line, dt FROM ods.raw_events;

-- dws aggregate: no partition, no owner
CREATE TABLE dws.agg_daily (
  day_total DECIMAL(16,2) COMMENT 'daily total'
);

INSERT INTO dws.agg_daily
SELECT SUM(pay_amount) FROM dwd.fact_orders;

-- layer mismatch: an ods_ table living in dwd
CREATE TABLE dwd.ods_leftover (
  oid BIGINT COMMENT 'legacy id'
) PARTITIONED BY (dt STRING COMMENT 'p');

-- orphan: written but never read downstream
CREATE TABLE dwd.dead_end (
  snapshot STRING COMMENT 'nobody reads this'
) PARTITIONED BY (dt STRING COMMENT 'p');

INSERT INTO dwd.dead_end SELECT line, dt FROM ods.raw_events;

-- dangling: defined, never in any lineage
CREATE TABLE dim.dim_ghost (
  gid BIGINT COMMENT 'ghost id'
) TBLPROPERTIES ('owner' = 'team-demo');
