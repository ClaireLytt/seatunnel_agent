-- Intentionally incompatible: custom UDF + Hive write-side hints
SELECT
  dt,
  decrypt_phone(phone_enc) AS phone,
  item
FROM dwd.orders_di
LATERAL VIEW explode(split(items, ',')) x AS item
DISTRIBUTE BY dt
SORT BY dt;
