-- refresh the user dimension from the raw landing table
INSERT OVERWRITE TABLE ods.users
SELECT user_id, user_name, region, updated_at
FROM staging.users_raw
WHERE dt = '${hiveconf:dt}';
