-- 口径一致性演示 · 同名字段取自不同来源列：contact ← phone vs contact ← email
INSERT OVERWRITE TABLE ads.notify_list_sms
SELECT u.user_id, u.phone AS contact, u.dt
FROM dwd.dim_user u;

INSERT OVERWRITE TABLE ads.notify_list_mail
SELECT u.user_id, u.email AS contact, u.dt
FROM dwd.dim_user u;
