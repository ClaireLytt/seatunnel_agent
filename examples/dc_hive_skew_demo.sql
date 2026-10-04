-- ============================================================================
-- 数据倾斜演练表(Hive)· dc_test_skewc_a / dc_test_skewc_b(各 2000 行)
-- A 侧重度倾斜,B 侧均匀 —— 专测比对页「数据倾斜」卡片的判定与对比:
--   * region:      A 侧 north 占 80%(1600/2000),east 10%/south 5%/west 5%
--                  B 侧四区各 25%
--   * merchant_id: A 侧热点商户 M001 占 60%(1200/2000),其余尾部 100 商户均摊
--                  B 侧 100 商户各 1%(20/2000)
--   * 行数/金额两侧一致(总量对比不干扰倾斜观察)
-- 服务端 posexplode 生成,秒级建表;清理:
--   DROP TABLE IF EXISTS dc_test_skewc_a; DROP TABLE IF EXISTS dc_test_skewc_b;
-- ============================================================================

DROP TABLE IF EXISTS dc_test_skewc_a;
CREATE TABLE dc_test_skewc_a AS
SELECT
  pos + 1                                            AS id,
  CASE WHEN pos < 1600 THEN 'north'
       WHEN pos < 1800 THEN 'east'
       WHEN pos < 1900 THEN 'south'
       ELSE 'west' END                               AS region,
  CASE WHEN pos < 1200 THEN 'M001'
       ELSE concat('M', lpad(cast(pmod(pos, 100) + 2 as string), 3, '0'))
       END                                           AS merchant_id,
  cast(pmod(pos * 37, 500) + 10 as double)           AS amount,
  concat('2024-06-0', cast(pmod(pos, 4) + 1 as string)) AS dt
FROM (SELECT posexplode(split(space(1999), ' ')) AS (pos, x)) t;

DROP TABLE IF EXISTS dc_test_skewc_b;
CREATE TABLE dc_test_skewc_b AS
SELECT
  pos + 1                                            AS id,
  CASE pmod(pos, 4) WHEN 0 THEN 'north'
                    WHEN 1 THEN 'east'
                    WHEN 2 THEN 'south'
                    ELSE 'west' END                  AS region,
  concat('M', lpad(cast(pmod(pos, 100) + 1 as string), 3, '0')) AS merchant_id,
  cast(pmod(pos * 37, 500) + 10 as double)           AS amount,
  concat('2024-06-0', cast(pmod(pos, 4) + 1 as string)) AS dt
FROM (SELECT posexplode(split(space(1999), ' ')) AS (pos, x)) t;
