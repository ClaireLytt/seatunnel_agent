-- ============================================================================
-- Data Comparison 功能测试数据（Hive）
-- 用法：整段复制到 beeline / Hive CLI 执行（需 Hive 2.x+，支持 INSERT VALUES）
-- 所有表以 dc_test_ 开头；文件末尾附清理语句
-- 如需指定库，请先执行：USE cladata;
-- ============================================================================

-- ────────────────────────────────────────────────────────────────────────────
-- 1. 主测试对：订单表（主键 id）
--    预置差异（清单中的预期结果依赖这些设计，请勿改动数据）：
--    * A 10 行（id 1-10）；B 9 行（id 1-8, 11）→ 行数 10 vs 9
--    * B 缺失 id=9,10；B 多出 id=11
--    * 修改行：id=3 amount 300.00→350.00；id=5 status paid→refund
--    * NULL：B 中 id=7,8 的 email 为 NULL（画像空值率 A=0%，B≈22%）
--    * 质量规则违规：B id=11 amount=1500（超出 0-1000）；email not_null 77.8%<80
--    * 敏感列：phone / email / id_card（脱敏检测）
--    * 水位线列：update_time（增量对比用 '2024-06-05 00:00:00'）
--    * 分层列：category（分层采样）
-- ────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS dc_test_orders_a;
CREATE TABLE dc_test_orders_a (
  id          INT,
  order_no    STRING,
  category    STRING,
  amount      DOUBLE,
  status      STRING,
  phone       STRING,
  email       STRING,
  id_card     STRING,
  update_time STRING
) STORED AS TEXTFILE;

INSERT INTO dc_test_orders_a VALUES
(1,  'ORD001', 'electronics', 100.00, 'paid',      '13800000001', 'u1@test.com',  '110101199001011234', '2024-06-01 10:00:00'),
(2,  'ORD002', 'clothing',    220.50, 'paid',      '13800000002', 'u2@test.com',  '110101199002021234', '2024-06-01 11:00:00'),
(3,  'ORD003', 'electronics', 300.00, 'paid',      '13800000003', 'u3@test.com',  '110101199003031234', '2024-06-02 09:30:00'),
(4,  'ORD004', 'food',         45.90, 'shipped',   '13800000004', 'u4@test.com',  '110101199004041234', '2024-06-02 14:00:00'),
(5,  'ORD005', 'clothing',    180.00, 'paid',      '13800000005', 'u5@test.com',  '110101199005051234', '2024-06-03 08:15:00'),
(6,  'ORD006', 'food',         62.30, 'cancelled', '13800000006', 'u6@test.com',  '110101199006061234', '2024-06-03 16:45:00'),
(7,  'ORD007', 'electronics', 999.99, 'paid',      '13800000007', 'u7@test.com',  '110101199007071234', '2024-06-04 10:20:00'),
(8,  'ORD008', 'books',        35.00, 'shipped',   '13800000008', 'u8@test.com',  '110101199008081234', '2024-06-04 18:00:00'),
(9,  'ORD009', 'books',        58.80, 'paid',      '13800000009', 'u9@test.com',  '110101199009091234', '2024-06-05 09:00:00'),
(10, 'ORD010', 'food',        120.00, 'paid',      '13800000010', 'u10@test.com', '110101199010101234', '2024-06-05 12:00:00');

DROP TABLE IF EXISTS dc_test_orders_b;
CREATE TABLE dc_test_orders_b (
  id          INT,
  order_no    STRING,
  category    STRING,
  amount      DOUBLE,
  status      STRING,
  phone       STRING,
  email       STRING,
  id_card     STRING,
  update_time STRING
) STORED AS TEXTFILE;

-- 若你的 Hive 版本不支持 VALUES 中的 NULL，可把含 NULL 的两行改为
-- INSERT INTO dc_test_orders_b SELECT 7, ..., CAST(NULL AS STRING), ... ;
INSERT INTO dc_test_orders_b VALUES
(1,  'ORD001', 'electronics',  100.00, 'paid',      '13800000001', 'u1@test.com', '110101199001011234', '2024-06-01 10:00:00'),
(2,  'ORD002', 'clothing',     220.50, 'paid',      '13800000002', 'u2@test.com', '110101199002021234', '2024-06-01 11:00:00'),
(3,  'ORD003', 'electronics',  350.00, 'paid',      '13800000003', 'u3@test.com', '110101199003031234', '2024-06-06 10:00:00'),
(4,  'ORD004', 'food',          45.90, 'shipped',   '13800000004', 'u4@test.com', '110101199004041234', '2024-06-02 14:00:00'),
(5,  'ORD005', 'clothing',     180.00, 'refund',    '13800000005', 'u5@test.com', '110101199005051234', '2024-06-06 11:00:00'),
(6,  'ORD006', 'food',          62.30, 'cancelled', '13800000006', 'u6@test.com', '110101199006061234', '2024-06-03 16:45:00'),
(7,  'ORD007', 'electronics',  999.99, 'paid',      '13800000007', NULL,          '110101199007071234', '2024-06-04 10:20:00'),
(8,  'ORD008', 'books',         35.00, 'shipped',   '13800000008', NULL,          '110101199008081234', '2024-06-04 18:00:00'),
(11, 'ORD011', 'electronics', 1500.00, 'paid',      '13800000011', 'u11@test.com','110101199011111234', '2024-06-06 12:00:00');

-- ────────────────────────────────────────────────────────────────────────────
-- 2. 结构差异对（结构对比 / 列映射 name:user_name）
--    * B 的 name 改名为 user_name；amount 类型 DOUBLE→DECIMAL(10,2)；B 多 remark 列
--    * 数据差异：id=2 amount 20.0 vs 21.0
-- ────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS dc_test_schema_a;
CREATE TABLE dc_test_schema_a (
  id      INT,
  name    STRING,
  amount  DOUBLE,
  created STRING
) STORED AS TEXTFILE;

INSERT INTO dc_test_schema_a VALUES
(1, 'alice', 10.50, '2024-06-01'),
(2, 'bob',   20.00, '2024-06-01'),
(3, 'carol', 30.25, '2024-06-02');

DROP TABLE IF EXISTS dc_test_schema_b;
CREATE TABLE dc_test_schema_b (
  id        INT,
  user_name STRING,
  amount    DECIMAL(10,2),
  remark    STRING,
  created   STRING
) STORED AS TEXTFILE;

INSERT INTO dc_test_schema_b VALUES
(1, 'alice', 10.50, 'ok',    '2024-06-01'),
(2, 'bob',   21.00, 'check', '2024-06-01'),
(3, 'carol', 30.25, '',      '2024-06-02');

-- ────────────────────────────────────────────────────────────────────────────
-- 3. 指标对（数据倾斜 / 聚合 / 校验和 / 自定义聚合）
--    * A 的 region 严重倾斜：north×16, south×2, east×1, west×1（基尼系数高）
--    * B 的 region 均匀：north/south/east/west 各 5（基尼系数低）
--    * 数值差异：id=4 sales 40→44；id=15 sales 150→155
-- ────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS dc_test_metrics_a;
CREATE TABLE dc_test_metrics_a (
  id     INT,
  region STRING,
  sales  DOUBLE,
  qty    INT
) STORED AS TEXTFILE;

INSERT INTO dc_test_metrics_a VALUES
(1,  'north', 10.0,  2), (2,  'north', 20.0,  3), (3,  'north', 30.0,  4),
(4,  'north', 40.0,  5), (5,  'north', 50.0,  1), (6,  'north', 60.0,  2),
(7,  'north', 70.0,  3), (8,  'north', 80.0,  4), (9,  'north', 90.0,  5),
(10, 'north', 100.0, 1), (11, 'north', 110.0, 2), (12, 'north', 120.0, 3),
(13, 'north', 130.0, 4), (14, 'north', 140.0, 5), (15, 'north', 150.0, 1),
(16, 'north', 160.0, 2), (17, 'south', 170.0, 3), (18, 'south', 180.0, 4),
(19, 'east',  190.0, 5), (20, 'west',  200.0, 1);

DROP TABLE IF EXISTS dc_test_metrics_b;
CREATE TABLE dc_test_metrics_b (
  id     INT,
  region STRING,
  sales  DOUBLE,
  qty    INT
) STORED AS TEXTFILE;

INSERT INTO dc_test_metrics_b VALUES
(1,  'north', 10.0,  2), (2,  'north', 20.0,  3), (3,  'north', 30.0,  4),
(4,  'north', 44.0,  5), (5,  'north', 50.0,  1), (6,  'south', 60.0,  2),
(7,  'south', 70.0,  3), (8,  'south', 80.0,  4), (9,  'south', 90.0,  5),
(10, 'south', 100.0, 1), (11, 'east',  110.0, 2), (12, 'east',  120.0, 3),
(13, 'east',  130.0, 4), (14, 'east',  140.0, 5), (15, 'east',  155.0, 1),
(16, 'west',  160.0, 2), (17, 'west',  170.0, 3), (18, 'west',  180.0, 4),
(19, 'west',  190.0, 5), (20, 'west',  200.0, 1);

-- ────────────────────────────────────────────────────────────────────────────
-- 4. 分区对（分区比对，分区列 dt）
--    * A：06-01 5 行 / 06-02 5 行 / 06-03 5 行
--    * B：06-01 5 行 / 06-02 3 行 / 06-03 缺失
--    * 预期差异：0 / -2 / -5，总绝对差异 7
-- ────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS dc_test_part_a;
CREATE TABLE dc_test_part_a (
  id  INT,
  val DOUBLE
) PARTITIONED BY (dt STRING) STORED AS TEXTFILE;

INSERT INTO dc_test_part_a PARTITION (dt='2024-06-01') VALUES
(1, 1.1), (2, 2.2), (3, 3.3), (4, 4.4), (5, 5.5);
INSERT INTO dc_test_part_a PARTITION (dt='2024-06-02') VALUES
(6, 6.6), (7, 7.7), (8, 8.8), (9, 9.9), (10, 10.1);
INSERT INTO dc_test_part_a PARTITION (dt='2024-06-03') VALUES
(11, 11.1), (12, 12.2), (13, 13.3), (14, 14.4), (15, 15.5);

DROP TABLE IF EXISTS dc_test_part_b;
CREATE TABLE dc_test_part_b (
  id  INT,
  val DOUBLE
) PARTITIONED BY (dt STRING) STORED AS TEXTFILE;

INSERT INTO dc_test_part_b PARTITION (dt='2024-06-01') VALUES
(1, 1.1), (2, 2.2), (3, 3.3), (4, 4.4), (5, 5.5);
INSERT INTO dc_test_part_b PARTITION (dt='2024-06-02') VALUES
(6, 6.6), (7, 7.7), (8, 8.8);

-- ────────────────────────────────────────────────────────────────────────────
-- 5. 完全一致对（验证绿色 Match 路径：行数 / 校验和 / 画像全一致）
-- ────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS dc_test_same_a;
CREATE TABLE dc_test_same_a (
  id    INT,
  name  STRING,
  score DOUBLE
) STORED AS TEXTFILE;

INSERT INTO dc_test_same_a VALUES
(1, 'aa', 90.5), (2, 'bb', 80.0), (3, 'cc', 70.5), (4, 'dd', 60.0), (5, 'ee', 95.0);

DROP TABLE IF EXISTS dc_test_same_b;
CREATE TABLE dc_test_same_b (
  id    INT,
  name  STRING,
  score DOUBLE
) STORED AS TEXTFILE;

INSERT INTO dc_test_same_b VALUES
(1, 'aa', 90.5), (2, 'bb', 80.0), (3, 'cc', 70.5), (4, 'dd', 60.0), (5, 'ee', 95.0);

-- ============================================================================
-- 验证建表结果
-- ============================================================================
SHOW TABLES LIKE 'dc_test*';
SELECT 'orders_a' AS t, COUNT(*) AS n FROM dc_test_orders_a
UNION ALL SELECT 'orders_b', COUNT(*) FROM dc_test_orders_b
UNION ALL SELECT 'schema_a', COUNT(*) FROM dc_test_schema_a
UNION ALL SELECT 'schema_b', COUNT(*) FROM dc_test_schema_b
UNION ALL SELECT 'metrics_a', COUNT(*) FROM dc_test_metrics_a
UNION ALL SELECT 'metrics_b', COUNT(*) FROM dc_test_metrics_b
UNION ALL SELECT 'part_a', COUNT(*) FROM dc_test_part_a
UNION ALL SELECT 'part_b', COUNT(*) FROM dc_test_part_b
UNION ALL SELECT 'same_a', COUNT(*) FROM dc_test_same_a
UNION ALL SELECT 'same_b', COUNT(*) FROM dc_test_same_b;
-- 预期行数：orders 10/9, schema 3/3, metrics 20/20, part 15/8, same 5/5

-- ============================================================================
-- 清理（测试完成后按需执行）
-- ============================================================================
-- DROP TABLE IF EXISTS dc_test_orders_a;
-- DROP TABLE IF EXISTS dc_test_orders_b;
-- DROP TABLE IF EXISTS dc_test_schema_a;
-- DROP TABLE IF EXISTS dc_test_schema_b;
-- DROP TABLE IF EXISTS dc_test_metrics_a;
-- DROP TABLE IF EXISTS dc_test_metrics_b;
-- DROP TABLE IF EXISTS dc_test_part_a;
-- DROP TABLE IF EXISTS dc_test_part_b;
-- DROP TABLE IF EXISTS dc_test_same_a;
-- DROP TABLE IF EXISTS dc_test_same_b;
