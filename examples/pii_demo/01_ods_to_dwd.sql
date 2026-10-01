-- ODS → DWD：手机号/身份证直接复制（未脱敏扩散 → 扫描报告应升级严重度）
INSERT OVERWRITE TABLE dwd.dim_user
SELECT
  u.user_id,
  u.user_name,
  u.phone,
  u.id_card_no,
  u.email,
  u.home_addr,
  u.dt
FROM ods.user_info u
WHERE u.dt = '2024-01-01';
