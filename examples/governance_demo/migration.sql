-- Migration demo: dangerous operations the guard grades and reverses.
ALTER TABLE dwd.fact_orders ADD COLUMNS (channel STRING COMMENT 'channel');
ALTER TABLE dwd.fact_orders CHANGE COLUMN memo memo VARCHAR(64);
ALTER TABLE dwd.ods_leftover RENAME TO dwd.legacy_leftover;
ALTER TABLE dwd.dead_end DROP COLUMN snapshot;
DROP TABLE dim.dim_ghost;
TRUNCATE TABLE dws.agg_daily;
