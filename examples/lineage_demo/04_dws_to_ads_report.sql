-- DWS -> ADS: 城市 GMV 大盘（两个上游汇合）
CREATE TABLE ads.city_gmv_report AS
SELECT
    g.stat_date,
    g.city,
    g.gmv,
    g.buyer_cnt,
    round(g.gmv / g.buyer_cnt, 2) AS avg_amount
FROM dws.gmv_daily g;

INSERT INTO ads.top_users
SELECT user_id, total_amount
FROM dws.user_stats
WHERE total_amount > 10000;
