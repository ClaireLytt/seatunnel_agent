/* Intentionally incompatible: custom UDF + Hive write-side hints */
SELECT
  dt,
  DECRYPT_PHONE(phone_enc) AS phone,
  item
FROM dwd.orders_di
LATERAL VIEW
EXPLODE(SPLIT_BY_STRING(items, ',')) x AS item;
