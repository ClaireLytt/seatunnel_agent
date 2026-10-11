-- 格式化演示：挤在一行的乱排版 SQL（含裸 SELECT *）
insert overwrite table ads.gmv_report select u.user_id,u.user_name,sum(o.amount) as gmv,count(1) as order_cnt from dwd.user_info u join dwd.orders o on u.user_id=o.user_id where o.dt='2024-01-01' and o.status in ('PAID','DONE') group by u.user_id,u.user_name;
select * from ads.gmv_report where dt = '2024-01-01';
