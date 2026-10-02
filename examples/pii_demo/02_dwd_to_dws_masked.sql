-- DWD → DWS：敏感列经 md5 / mask 处理后落表（已脱敏扩散，不升级严重度）
INSERT OVERWRITE TABLE dws.user_profile
SELECT
  d.user_id,
  md5(d.phone)          AS phone_md5,
  sha2(d.id_card_no, 256) AS id_card_hash,
  substr(d.email, 1, 3) AS email_prefix,
  d.dt
FROM dwd.dim_user d;
