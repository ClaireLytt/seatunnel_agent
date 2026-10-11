-- DAG 体检演示 · 断链与死作业：
-- dwd.missing_src 没有任何作业产出（悬空上游）；
-- dws.dead_metric 产出后没有任何下游消费（死作业）
INSERT OVERWRITE TABLE ads.broken_report
SELECT user_id, score FROM dwd.missing_src;

INSERT OVERWRITE TABLE dws.dead_metric
SELECT user_id, count(1) AS cnt FROM dwd.orders GROUP BY user_id;
