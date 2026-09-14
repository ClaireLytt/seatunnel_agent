# Text2SQL (Chat BI) Agent — Test Document

> Version: 1.0  
> Date: 2026-09-14  
> Module: `src/seatunnel_agent/text2sql/`  
> Test file: `tests/test_text2sql.py`

---

## 1. Overview

This document describes the complete testing strategy for the Text2SQL (Chat BI) agent feature. The Text2SQL agent translates natural-language questions (Chinese/English) into safe Hive SQL, executes them against HiveServer2, and exports results as CSV.

### 1.1 Test Scope

| Layer | Module | Description |
|-------|--------|-------------|
| Schema Parsing | `schema.py` | DDL parsing, column/table comment extraction, partition detection |
| SQL Validation | `validator.py` | SELECT-only enforcement, table whitelist, stacked query prevention, column validation |
| Table/Column Matching | `matcher.py` | Keyword tokenization, CJK n-gram matching, scoring, tie-breaking |
| Partition Rules | `partition.py` | Table suffix classification, time range extraction, partition clause generation |
| CSV Export | `exporter.py` | UTF-8 BOM output, directory/file path handling |
| Query Logging | `qlog.py` | JSONL structured logging, recent query retrieval |
| Tool Layer | `tools.py` | Tool handler dispatch, runtime state, partition enforcement |
| Hive Execution | `executor.py` | Connection management, result capping, partition cache |
| Agent Loop | `agent.py` | ReAct loop, event emission, multi-turn conversation |
| UI Integration | `text2sql_ui.py` | Gradio page, streaming events, sidebar controls |

### 1.2 Test Types

- **Unit Tests** (automated): 62 tests in `tests/test_text2sql.py`, covering all non-Hive layers
- **Integration Tests** (manual): Require a live HiveServer2 connection
- **End-to-End Tests** (manual): Full agent loop through the Gradio UI

---

## 2. Environment Setup

### 2.1 Automated Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run all Text2SQL tests
pytest tests/test_text2sql.py -v

# Run with coverage
pytest tests/test_text2sql.py --cov=seatunnel_agent.text2sql --cov-report=term-missing
```

No external dependencies required — Hive connections are either mocked or skipped.

### 2.2 Integration Tests (Hive Required)

```bash
# Install Hive support
pip install pyhive thrift

# Configure .env
HIVE_HOST=10.0.0.1
HIVE_PORT=10000
HIVE_DATABASE=default
HIVE_USERNAME=readonly_user
HIVE_TIMEOUT=300
SCHEMA_DDL_PATH=config/schema_ddl.sql
```

### 2.3 End-to-End Tests (Full Stack)

```bash
# Install all dependencies
pip install -e ".[all,ui]"

# Configure .env with both LLM and Hive settings
# Then launch UI
seatunnel-agent ui
# Navigate to the "Text2SQL" page
```

---

## 3. Automated Unit Tests

### 3.1 Test Summary (62 tests)

| Test Class | Count | Module Under Test |
|------------|-------|-------------------|
| `TestParseDDL` | 5 | `schema.py` |
| `TestValidateSQL` | 7 | `validator.py` |
| `TestEnforceLimit` | 3 | `validator.py` |
| `TestMatcher` | 5 | `matcher.py` |
| `TestPartition` | 9 | `partition.py` |
| `TestExportAndLog` | 3 | `exporter.py`, `qlog.py` |
| `TestValidateColumns` | 5 | `validator.py` |
| `TestPartitionEnforcement` | 3 | `tools.py` |
| `TestTools` | 7 | `tools.py` |
| `TestEdgeCases` | 11 | Cross-module edge cases |
| **Total** | **62** | |

### 3.2 Schema Parsing Tests (`TestParseDDL`)

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_parses_all_tables` | Parse DDL with 3 CREATE TABLE statements | 3 tables in store; case-insensitive lookup works |
| `test_table_comment_and_type` | Extract table comments and classify suffix | `_di` → "incremental", `_df` → "full", no suffix → "other" |
| `test_columns_with_complex_types` | Parse `decimal(10,2)`, `array<string>` types | Column names and types correctly extracted |
| `test_partition_columns` | Detect `PARTITIONED BY` clause | `is_partitioned=True`, partition column name = "pt" |
| `test_find_column_by_comment` | Look up column by Chinese comment text | Finds correct column by comment substring match |

### 3.3 SQL Validation Tests (`TestValidateSQL`)

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_valid_select` | Valid SELECT with partition filter | `ok=True`, table name extracted |
| `test_rejects_write_statements` | DROP/DELETE/UPDATE/INSERT/TRUNCATE/CREATE | `ok=False` for all 6 variants |
| `test_rejects_stacked_queries` | SQL with `;` separator (injection attempt) | `ok=False`, "Multiple SQL statements" error |
| `test_rejects_non_whitelisted_table` | SELECT from `secret.users` (not in schema) | `ok=False`, "whitelist" in error |
| `test_keyword_inside_string_literal_is_ok` | `WHERE name = 'drop table'` | `ok=True` (keyword in string literal ignored) |
| `test_cte_names_not_flagged` | CTE alias not treated as table name | `ok=True`, CTE alias excluded from table list |
| `test_extract_tables_join` | Extract tables from JOIN query | Both table names returned |

### 3.4 LIMIT Enforcement Tests (`TestEnforceLimit`)

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_appends_default_limit` | Query without LIMIT | `LIMIT 1000` appended |
| `test_keeps_existing_limit` | Query with `LIMIT 10` | Preserved as-is |
| `test_caps_excessive_limit` | `LIMIT 999999999` | Capped to `LIMIT 100000` |

### 3.5 Table/Column Matching Tests (`TestMatcher`)

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_tokenize_mixed` | Mixed Chinese/English input | English tokens and CJK n-grams extracted |
| `test_matches_by_chinese_comment` | Query with Chinese business terms | Top match is table with matching comment |
| `test_matches_by_english_name` | Query with exact table name | Exact-name table ranked first |
| `test_full_table_match` | Query with table comment + column terms | Correct table matched by comment + column hits |
| `test_match_columns_prefers_english_name` | Column name vs. comment match | English name match has priority |

### 3.6 Partition Rule Tests (`TestPartition`)

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_classify` | Table suffix classification | `_di` → incremental, `_hf` → full, plain → other |
| `test_extract_recent_days` | "最近30天" (recent 30 days) | Correct start/end date range |
| `test_extract_exact_date` | "20260312" (exact date) | Single-day range |
| `test_extract_chinese_date` | "2026年3月12日" | Parsed to date(2026, 3, 12) |
| `test_incremental_with_range` | Range on `_di` table | `pt >= '...' AND pt <= '...'` clause |
| `test_incremental_without_range_uses_max` | No range, max partition given | `pt = '<max>'` clause |
| `test_full_table_prefers_user_date` | `_df` table with user date | `pt = '<user_date>'` |
| `test_unpartitioned_returns_empty` | Table without PARTITIONED BY | Empty string returned |
| `test_has_partition_filter` | SQL with/without `pt =` | Correctly detects presence/absence |

### 3.7 Export & Logging Tests (`TestExportAndLog`)

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_export_csv_to_dir` | Export to directory with name hint | CSV created with BOM, Chinese content preserved |
| `test_export_csv_explicit_file` | Export to specific file path | File created at exact path |
| `test_query_logger_roundtrip` | Log a query and read it back | JSONL file contains valid JSON with all fields |

### 3.8 Column Validation Tests (`TestValidateColumns`)

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_valid_columns_no_warnings` | All columns exist in schema | Empty warnings list |
| `test_detects_nonexistent_column` | `SELECT fake_column FROM ...` | Warning about `fake_column` |
| `test_partition_column_not_flagged` | Partition column `pt` in WHERE | No false positive warning |
| `test_validate_sql_populates_column_warnings` | Full validation flow | `column_warnings` populated in ValidationResult |
| `test_no_warnings_for_empty_query` | `SELECT 1` (no table reference) | Empty warnings list |

### 3.9 Partition Enforcement Tests (`TestPartitionEnforcement`)

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_rejects_missing_partition_filter` | Query partitioned table without WHERE pt= | Error: "partition filter" |
| `test_accepts_query_with_partition_filter` | Query with `WHERE pt = '20260312'` | No partition-related error |
| `test_unpartitioned_table_no_enforcement` | Query on non-partitioned table | No enforcement applied |

### 3.10 Tool Layer Tests (`TestTools`)

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_match_tables_tool` | Call `match_tables` tool | Returns candidates with scores |
| `test_get_table_schema_tool` | Call `get_table_schema` tool | Returns full schema with columns, partition info |
| `test_get_table_schema_unknown_table` | Schema for non-existent table | Error response |
| `test_get_max_partition_unpartitioned` | Max partition on non-partitioned table | Error: "not partitioned" |
| `test_export_csv_no_result` | Export before any query | Error: "No query result" |
| `test_export_csv_with_result` | Export after setting `last_result` | CSV file created, success response |
| `test_unknown_tool` | Call non-existent tool name | Error: "Unknown tool" |

### 3.11 Edge Case Tests (`TestEdgeCases`)

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_cte_with_join` | CTE + JOIN validation | `ok=True` |
| `test_extract_time_range_english` | "last 7 days" (English) | Correct 7-day range |
| `test_extract_time_range_past_days` | "past 14 days" (English) | Correct 14-day range |
| `test_extract_time_range_no_match` | "所有学生信息" (no time reference) | `is_empty=True` |
| `test_extract_time_range_month_day` | "3月12日" (month-day only) | Inferred to current year |
| `test_matcher_empty_query` | Empty string query | Empty results list |
| `test_matcher_tie_breaks_by_column_hits` | Multiple tables with equal scores | Higher column hit count wins |
| `test_has_partition_filter_between` | `WHERE pt BETWEEN ...` | Detected as having filter |
| `test_has_partition_filter_in` | `WHERE pt IN (...)` | Detected as having filter |
| `test_enforce_limit_preserves_semicolons` | Input with trailing `;` | Semicolons stripped, LIMIT added |

---

## 4. Manual Integration Test Cases

These test cases require a live HiveServer2 connection and configured schema DDL.

### 4.1 Prerequisites

- HiveServer2 accessible from test machine
- `HIVE_HOST`, `HIVE_PORT`, `HIVE_DATABASE` configured in `.env`
- `config/schema_ddl.sql` populated with real table DDLs
- LLM API key configured for agent-level tests

### 4.2 Hive Connection Tests

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| I-01 | Successful connection | Set valid Hive credentials, call `executor.run("SELECT 1")` | Returns `QueryResult` with 1 row |
| I-02 | Connection failure | Set invalid host, attempt query | `RuntimeError` with descriptive message |
| I-03 | Query timeout | Set `HIVE_TIMEOUT=1`, run slow query | Timeout error after ~1 second |
| I-04 | Row cap enforcement | Query returning >1000 rows without explicit LIMIT | `truncated=True`, exactly 1000 rows |

### 4.3 Partition Cache Tests

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| I-05 | Get max partition | Call `executor.get_max_partition("db.table_di")` | Returns latest partition value (e.g., "20260913") |
| I-06 | Cache hit | Call same table twice | Second call returns instantly (cached) |
| I-07 | Cache refresh | Call with `refresh=True` | Re-queries Hive, updates cache |
| I-08 | Empty table | Call on partitioned table with no data | `RuntimeError`: "has no partitions" |

### 4.4 SQL Safety Tests (Live)

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| I-09 | Write rejection (live) | Submit `DROP TABLE ...` through execute_sql tool | Rejected before reaching Hive |
| I-10 | Whitelist enforcement (live) | Submit query on table not in DDL file | Rejected: "not in the schema whitelist" |
| I-11 | Partition enforcement (live) | Submit query on partitioned table without pt= | Rejected: "missing partition filter" |
| I-12 | Stacked query prevention | Submit `SELECT 1; DROP TABLE ...` | Rejected: "Multiple SQL statements" |

---

## 5. Manual End-to-End Test Cases

These tests exercise the full agent loop through the Gradio UI.

### 5.1 UI Navigation

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| E-01 | Text2SQL page loads | Launch UI, click "Text2SQL" | Page renders with sidebar, chat area, input box |
| E-02 | Hive connection status | Fill Hive fields in sidebar, click Connect | Status shows connected or error message |
| E-03 | Schema table list | After connection, check sidebar | Shows loaded table names from DDL file |

### 5.2 Simple Query Flow

| ID | Test Case | Input | Expected Result |
|----|-----------|-------|-----------------|
| E-04 | Single table query | "查询学生表中所有学生信息" | Generates `SELECT * FROM atest.student LIMIT 1000` |
| E-05 | Partitioned table query | "查询最近7天供应链入库明细" | Agent calls `get_max_partition`, generates SQL with `pt >=` filter |
| E-06 | Full table query | "查询供应链效率归因表中商品一级类目的入库量" | Uses latest partition, includes `GROUP BY level1_category_name` |
| E-07 | Exact date query | "查询20260312的入库数据" | SQL contains `pt = '20260312'` |

### 5.3 Complex Query Flow

| ID | Test Case | Input | Expected Result |
|----|-----------|-------|-----------------|
| E-08 | Multi-table JOIN | "关联全流程明细表和归因分析表，查询各类目入库量对比" | JOIN with partition pushdown on both tables |
| E-09 | Aggregation query | "统计各品牌最近30天的入库总量" | `SUM(inbound_cnt) GROUP BY brand_name` with date range |
| E-10 | Window function | "计算每个仓库每天的入库量排名" | `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)` |
| E-11 | Time range query | "2026年3月1日到3月13日各仓库的入库量趋势" | `pt >= '20260301' AND pt <= '20260313'` with GROUP BY pt |

### 5.4 Safety & Error Handling

| ID | Test Case | Input | Expected Result |
|----|-----------|-------|-----------------|
| E-12 | Write attempt | "删除学生表中id=1的记录" | Agent refuses: only SELECT allowed |
| E-13 | Unknown table | "查询salary_table中员工薪资" | Agent reports table not in whitelist |
| E-14 | Column hallucination check | Agent generates SQL with non-existent column | Column warning shown, agent self-corrects |
| E-15 | Partition filter omission | User asks for "all data" without time range | Agent calls `get_max_partition` before executing |

### 5.5 CSV Export

| ID | Test Case | Input | Expected Result |
|----|-----------|-------|-----------------|
| E-16 | Default export | After a query, "导出CSV" | CSV saved to Desktop with timestamped name |
| E-17 | Custom path export | "导出到 D:\output\result.csv" | CSV saved to specified path |
| E-18 | Chinese content export | Query with Chinese column aliases | CSV opens correctly in Excel (UTF-8 BOM) |
| E-19 | Export without query | "导出CSV" (no prior query) | Error: "No query result to export" |

### 5.6 Multi-Turn Conversation

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| E-20 | Context memory | Ask "查询学生信息", then "加上年龄过滤 > 18" | Second query references same table without re-matching |
| E-21 | Re-export | After a query, "再导出一次" | Exports same result without re-querying |
| E-22 | New topic | After student query, ask "查询供应链入库量" | Agent matches new table, no carryover from previous |

### 5.7 Agent Workflow Verification

| ID | Test Case | Verification Point | Expected Behavior |
|----|-----------|-------------------|-------------------|
| E-23 | Tool call sequence | Observe agent thinking panel | match_tables → get_table_schema → (get_max_partition) → execute_sql |
| E-24 | Streaming display | Watch chat during agent execution | Real-time thinking, tool calls, results displayed |
| E-25 | Error recovery | Agent generates bad SQL on first try | Agent reads error, corrects SQL, retries |
| E-26 | Max iteration limit | Force agent into infinite loop scenario | Stops at 15 iterations with timeout message |

---

## 6. Performance Test Cases

| ID | Test Case | Metric | Threshold |
|----|-----------|--------|-----------|
| P-01 | Schema parsing speed | Parse 100-table DDL file | < 500ms |
| P-02 | Table matching speed | Match against 100 tables | < 100ms |
| P-03 | SQL validation speed | Validate complex SQL | < 10ms |
| P-04 | Hive query timeout | Query with HIVE_TIMEOUT=300 | Aborts after configured timeout |
| P-05 | Row cap memory | Query returning max rows (100,000) | Memory usage < 500MB |
| P-06 | CSV export speed | Export 100,000 rows | < 10 seconds |

---

## 7. Security Test Cases

| ID | Test Case | Attack Vector | Expected Defense |
|----|-----------|---------------|-----------------|
| S-01 | SQL injection via semicolons | `; DROP TABLE ...` | Stacked query detection blocks |
| S-02 | SQL injection via comments | `/* */ DELETE FROM ...` | First-word check catches non-SELECT |
| S-03 | DDL via CTAS | `CREATE TABLE x AS SELECT ...` | `create` in forbidden keywords |
| S-04 | Privilege escalation | `GRANT ALL ON ...` | `grant` in forbidden keywords |
| S-05 | Data exfiltration | `EXPORT TABLE ...` | `export` in forbidden keywords |
| S-06 | Table whitelist bypass | Query table not in `schema_ddl.sql` | SchemaStore whitelist enforcement |
| S-07 | Unbounded scan | `SELECT * FROM huge_table` | Auto LIMIT enforcement (max 100,000) |
| S-08 | Full partition scan | Query partitioned table without filter | Partition filter enforcement blocks |
| S-09 | Keyword in string literal | `WHERE name = 'drop table'` | String literal stripping prevents false positive |
| S-10 | Keyword in identifier | `dataset`, `insert_time` column names | Word-boundary tokenization avoids false match |

---

## 8. Test Execution & Reporting

### 8.1 Running Automated Tests

```bash
# Run all Text2SQL tests with verbose output
pytest tests/test_text2sql.py -v

# Run specific test class
pytest tests/test_text2sql.py::TestValidateSQL -v

# Run single test
pytest tests/test_text2sql.py::TestPartitionEnforcement::test_rejects_missing_partition_filter -v

# Coverage report
pytest tests/test_text2sql.py --cov=seatunnel_agent.text2sql --cov-report=html
```

### 8.2 Expected Results

```
tests/test_text2sql.py::TestParseDDL::test_parses_all_tables PASSED
tests/test_text2sql.py::TestParseDDL::test_table_comment_and_type PASSED
tests/test_text2sql.py::TestParseDDL::test_columns_with_complex_types PASSED
tests/test_text2sql.py::TestParseDDL::test_partition_columns PASSED
tests/test_text2sql.py::TestParseDDL::test_find_column_by_comment PASSED
tests/test_text2sql.py::TestValidateSQL::test_valid_select PASSED
tests/test_text2sql.py::TestValidateSQL::test_rejects_write_statements[...] PASSED (x6)
tests/test_text2sql.py::TestValidateSQL::test_rejects_stacked_queries PASSED
tests/test_text2sql.py::TestValidateSQL::test_rejects_non_whitelisted_table PASSED
tests/test_text2sql.py::TestValidateSQL::test_keyword_inside_string_literal_is_ok PASSED
tests/test_text2sql.py::TestValidateSQL::test_cte_names_not_flagged PASSED
tests/test_text2sql.py::TestValidateSQL::test_extract_tables_join PASSED
tests/test_text2sql.py::TestEnforceLimit::test_appends_default_limit PASSED
tests/test_text2sql.py::TestEnforceLimit::test_keeps_existing_limit PASSED
tests/test_text2sql.py::TestEnforceLimit::test_caps_excessive_limit PASSED
... (62 tests total, all PASSED)
```

### 8.3 Known Issues

| Issue | Status | Impact |
|-------|--------|--------|
| `test_llm.py::test_format` fails (pre-existing) | Known | Unrelated to Text2SQL; `_convert_tools_to_openai()` signature mismatch |
| Column validation is regex-based | By design | May miss aliases/computed expressions; returns warnings, not errors |
| No automated integration tests with Hive | Planned | Requires CI environment with HiveServer2; manual testing covers this gap |

---

## 9. Test Data

### 9.1 DDL Used in Automated Tests

The test fixture uses a simplified 3-table DDL (defined in `tests/test_text2sql.py`):

| Table | Type | Partitioned | Columns |
|-------|------|-------------|---------|
| `zz.dwm_scm_detail_di` | Incremental | Yes (`pt`) | 6 columns (inbound_id, warehouse_name, inbound_cnt, ...) |
| `zz.dws_scm_attribution_df` | Full | Yes (`pt`) | 2 columns (level1_category_name, scm_inbound_cnt) |
| `atest.student` | Other | No | 2 columns (id, name) |

### 9.2 Production Schema DDL

The production DDL is located at `config/schema_ddl.sql` and contains 4 tables:

| Table | Comment | Columns | Partitioned |
|-------|---------|---------|-------------|
| `zz.dwm_scm_detail_di` | dwm-供应链域-全流程明细表-增量表 | 62 | Yes (pt) |
| `zz.ads_scm_effect_attribution_analysis_target` | ads-供应链效率-供应链效率归因分析表 | 22 | Yes (pt) |
| `atest.student` | 学生信息表 | 3 | No |
| `atest.student2` | 学生成绩表 | 3 | No |

---

## 10. Appendix: Test Coverage Matrix

| PRD Section | Requirement | Test Coverage |
|-------------|-------------|---------------|
| §4 (Key Concepts) | Table suffix classification (_di/_hf/etc.) | `TestPartition::test_classify` |
| §6.1 (Table Matching) | Keyword + CJK fuzzy matching | `TestMatcher` (5 tests) |
| §6.2 (Schema Retrieval) | DDL parsing, column/comment extraction | `TestParseDDL` (5 tests) |
| §6.3 (Partition Rules) | Time range extraction, clause generation | `TestPartition` (9 tests) |
| §6.4 (SQL Generation) | LLM-based SQL generation | E-04 through E-11 (manual) |
| §6.5 (SQL Execution) | Hive query execution, row cap | I-01, I-04, P-04 (manual) |
| §6.6 (Result Display) | Preview rows, markdown table | E-24 (manual) |
| §6.7 (CSV Export) | UTF-8 BOM, timestamped filenames | `TestExportAndLog` + E-16~E-19 |
| §6.8 (Query Logging) | JSONL structured logs | `TestExportAndLog::test_query_logger_roundtrip` |
| §9 (Security) | SELECT-only, whitelist, LIMIT, partition | `TestValidateSQL` + `TestPartitionEnforcement` + S-01~S-10 |
| §10 (Non-functional) | Performance thresholds | P-01~P-06 (manual) |
| §11 (UI Integration) | Gradio page, streaming | E-01~E-03, E-24 (manual) |
| §13 (Risk: Hallucination) | Column existence validation | `TestValidateColumns` (5 tests) |





下面是你需要在 Hive 中执行的建表和插入数据的 SQL，直接复制到 Hive CLI 或 beeline 里运行：

```sql
-- 切到你的库
USE cladata;

-- 1. 学生表
CREATE TABLE IF NOT EXISTS student(
  id string COMMENT '学号',
  name string COMMENT '姓名',
  age int COMMENT '年龄',
  gender string COMMENT '性别',
  major string COMMENT '专业'
)
COMMENT '学生信息表'
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE;

INSERT INTO student VALUES
('S001', '张三', 20, '男', '计算机科学'),
('S002', '李四', 21, '女', '数据科学'),
('S003', '王五', 22, '男', '软件工程'),
('S004', '赵六', 20, '女', '计算机科学'),
('S005', '钱七', 23, '男', '人工智能'),
('S006', '孙八', 21, '女', '数据科学'),
('S007', '周九', 22, '男', '软件工程'),
('S008', '吴十', 20, '女', '人工智能');

-- 2. 课程表
CREATE TABLE IF NOT EXISTS course(
  course_id string COMMENT '课程编号',
  course_name string COMMENT '课程名称',
  teacher string COMMENT '授课老师',
  credit int COMMENT '学分'
)
COMMENT '课程信息表'
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE;

INSERT INTO course VALUES
('C001', '数据库原理', '刘教授', 4),
('C002', '机器学习', '陈教授', 3),
('C003', '操作系统', '王教授', 4),
('C004', 'Python编程', '李教授', 3),
('C005', '数据结构', '张教授', 4);

-- 3. 成绩表
CREATE TABLE IF NOT EXISTS score(
  id string COMMENT '学号',
  course_id string COMMENT '课程编号',
  score double COMMENT '成绩',
  semester string COMMENT '学期'
)
COMMENT '学生成绩表'
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE;

INSERT INTO score VALUES
('S001', 'C001', 92.5, '2026春'),
('S001', 'C002', 88.0, '2026春'),
('S002', 'C001', 95.0, '2026春'),
('S002', 'C003', 78.5, '2026春'),
('S003', 'C002', 85.0, '2026春'),
('S003', 'C004', 91.0, '2026春'),
('S004', 'C001', 76.0, '2026春'),
('S004', 'C005', 89.5, '2026春'),
('S005', 'C002', 93.0, '2026春'),
('S005', 'C003', 82.0, '2026春'),
('S006', 'C004', 87.5, '2026春'),
('S007', 'C005', 94.0, '2026春'),
('S008', 'C001', 90.0, '2026春');

-- 4. 销售表（分区表）
CREATE TABLE IF NOT EXISTS sales_di(
  order_id string COMMENT '订单编号',
  product_name string COMMENT '商品名称',
  category string COMMENT '商品类目',
  amount double COMMENT '订单金额',
  quantity int COMMENT '购买数量',
  city string COMMENT '城市',
  customer_id string COMMENT '客户编号'
)
COMMENT '销售订单明细表-增量'
PARTITIONED BY (pt string COMMENT '业务日期yyyyMMdd')
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE;

-- 插入 3 天的销售数据
INSERT INTO sales_di PARTITION(pt='20260912') VALUES
('D001', 'iPhone 15', '手机', 5999.0, 1, '北京', 'U001'),
('D002', 'MacBook Pro', '电脑', 14999.0, 1, '上海', 'U002'),
('D003', '小米耳机', '配件', 199.0, 3, '广州', 'U003');

INSERT INTO sales_di PARTITION(pt='20260913') VALUES
('D004', 'iPad Air', '平板', 4599.0, 1, '北京', 'U001'),
('D005', 'AirPods', '配件', 1299.0, 2, '深圳', 'U004'),
('D006', 'ThinkPad', '电脑', 8999.0, 1, '上海', 'U005'),
('D007', '华为手机', '手机', 4999.0, 1, '广州', 'U002');

INSERT INTO sales_di PARTITION(pt='20260914') VALUES
('D008', 'Surface Pro', '平板', 9999.0, 1, '北京', 'U003'),
('D009', '机械键盘', '配件', 599.0, 2, '深圳', 'U006'),
('D010', 'iPhone 15', '手机', 5999.0, 1, '上海', 'U001'),
('D011', '显示器', '配件', 2499.0, 1, '广州', 'U004');
```

建完表之后，启动 UI 测试这些查询：

| 测试问题                | 预期效果                                          |
| ----------------------- | ------------------------------------------------- |
| "查询所有学生信息"      | 查 student 表，返回 8 条                          |
| "成绩最高的3个学生"     | JOIN score + student，ORDER BY score DESC LIMIT 3 |
| "各专业的学生人数"      | GROUP BY major + COUNT                            |
| "查询最近3天的销售数据" | sales_di 表，自动加分区过滤                       |
| "每个城市的销售总额"    | GROUP BY city + SUM(amount)，带分区条件           |
| "哪个商品类目卖得最多"  | GROUP BY category + SUM(quantity)                 |

建好表后告诉我，我帮你启动 UI 测试。